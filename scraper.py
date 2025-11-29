#!/usr/bin/env python3
"""
Scraper para Mestre Parrilleros - Versão Completa
Extrai TODOS os produtos de todas as categorias com paginação
Integração com PostgreSQL
Autor: Gabriel Sezaltino
Data: 2025-01-27
"""

import json
import asyncio
import re
import os
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page
import sys

# Carregar variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv não instalado, usar apenas variáveis de ambiente do sistema

# Configurações
DEBUG = True  # Mude para False em produção
TIMEOUT = 30000  # 30 segundos

# URLs das categorias para scraping completo
CATEGORIAS = [
    {
        'nome': 'Churrasqueiras e Parrillas',
        'url': 'https://www.lojamestreparrillero.com.br/churrasqueiraseparrillas',
        'slug': 'churrasqueiraseparrillas'
    },
    {
        'nome': 'Bancada de Embutir',
        'url': 'https://www.lojamestreparrillero.com.br/bancadadeembutir',
        'slug': 'bancadadeembutir'
    },
    {
        'nome': 'Churrasqueiras para Alvenaria',
        'url': 'https://www.lojamestreparrillero.com.br/churrasqueirasparaalvenaria',
        'slug': 'churrasqueirasparaalvenaria'
    },
    {
        'nome': 'Bancada',
        'url': 'https://www.lojamestreparrillero.com.br/bancada',
        'slug': 'bancada'
    },
    {
        'nome': 'Portátil Externa',
        'url': 'https://www.lojamestreparrillero.com.br/portatilexterna',
        'slug': 'portatilexterna'
    },
    {
        'nome': 'Sem Fumaça',
        'url': 'https://www.lojamestreparrillero.com.br/semfumaca',
        'slug': 'semfumaca'
    },
    {
        'nome': 'Acessórios',
        'url': 'https://www.lojamestreparrillero.com.br/acessorios',
        'slug': 'acessorios'
    }
]

# Configuração do banco de dados (via variáveis de ambiente)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'mestre_parrillero'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

MAX_RETRIES = 3  # Número máximo de tentativas em caso de erro

def log(message, level="INFO"):
    """Log formatado"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def limpar_preco(preco_str: str) -> Dict[str, any]:
    """
    Limpa string de preço e extrai valor numérico
    Exemplos:
        'R$ R$ 1.510,40' -> {'texto': 'R$ 1.510,40', 'valor': 1510.40}
        'R$ 7.450,00' -> {'texto': 'R$ 7.450,00', 'valor': 7450.00}
    """
    if not preco_str or preco_str == 'Consultar':
        return {'texto': 'Consultar', 'valor': None}

    # Remover duplicatas de R$, espaços extras e quebras de linha
    preco_limpo = re.sub(r'R\$\s*R\$', 'R$', preco_str)
    preco_limpo = re.sub(r'\s+', ' ', preco_limpo).strip()

    # Extrair apenas o valor numérico para conversão
    match = re.search(r'([\d.]+,\d{2})', preco_limpo)
    if match:
        valor_str = match.group(1)
        # Converter para float (remover pontos e substituir vírgula por ponto)
        valor_float = float(valor_str.replace('.', '').replace(',', '.'))
        return {
            'texto': preco_limpo,
            'valor': valor_float
        }

    return {'texto': preco_limpo, 'valor': None}

async def detectar_total_paginas(page: Page) -> int:
    """Detecta o número total de páginas na paginação"""
    try:
        # Tentar encontrar elementos de paginação
        total_paginas = await page.evaluate('''
            () => {
                // Procurar pelo último número de página
                const paginacaoLinks = document.querySelectorAll('.paginacao a, .pagination a, [class*="pag"] a');
                let maxPagina = 1;

                paginacaoLinks.forEach(link => {
                    const texto = link.textContent.trim();
                    const numero = parseInt(texto);
                    if (!isNaN(numero) && numero > maxPagina) {
                        maxPagina = numero;
                    }
                });

                // Também verificar se existe "próxima" ou "última" página
                const urlParams = new URLSearchParams(window.location.search);
                const paginaAtual = parseInt(urlParams.get('pagina')) || 1;

                return Math.max(maxPagina, paginaAtual);
            }
        ''')

        return max(1, total_paginas)
    except:
        return 1

async def extrair_produtos_pagina(page: Page, categoria_nome: str) -> List[Dict]:
    """Extrai produtos de uma única página"""
    produtos = await page.evaluate('''
        () => {
            const items = [];
            const productElements = document.querySelectorAll('li .listagem-item');

            productElements.forEach((product, index) => {
                try {
                    const nomeEl = product.querySelector('.nome-produto');
                    const nome = nomeEl?.textContent?.trim() || '';

                    const linkEl = product.querySelector('.produto-sobrepor') || product.querySelector('a[href]');
                    const link = linkEl?.href || '';

                    let preco = '';
                    const precoEl = product.querySelector('.preco-venda');
                    if (precoEl) {
                        preco = 'R$ ' + precoEl.textContent?.trim();
                    }

                    if (!preco) {
                        const precoParceladoEl = product.querySelector('.preco-parcela strong.cor-principal');
                        if (precoParceladoEl) {
                            preco = precoParceladoEl.textContent?.trim();
                        }
                    }

                    const imgEl = product.querySelector('.imagem-principal');
                    const imagem = imgEl?.src || imgEl?.dataset?.src || '';

                    const prodId = product.dataset?.id || product.className?.match(/prod-id-(\\d+)/)?.[1] || '';

                    const skuEl = product.querySelector('.produto-sku');
                    const sku = skuEl?.textContent?.trim() || '';

                    if (nome && link) {
                        items.push({
                            id: prodId || '',
                            sku: sku,
                            nome: nome,
                            preco: preco || 'Consultar',
                            imagem: imagem,
                            link: link,
                            metodo_extracao: '.listagem-item'
                        });
                    }
                } catch (err) {
                    console.error(`Erro ao processar produto ${index}:`, err);
                }
            });

            return items;
        }
    ''')

    # Adicionar categoria e limpar preços
    timestamp = datetime.now().isoformat()
    for produto in produtos:
        produto['categoria'] = categoria_nome

        # Limpar preço
        preco_info = limpar_preco(produto['preco'])
        produto['preco_texto'] = preco_info['texto']
        produto['preco_valor'] = preco_info['valor']

        produto['data_scraping'] = timestamp
        produto['status'] = 'Disponível'

    return produtos

async def scrape_categoria_com_paginacao(page: Page, categoria: Dict, max_paginas: int = 20) -> List[Dict]:
    """Scrape uma categoria completa com todas as páginas"""
    log(f"📁 Iniciando scraping da categoria: {categoria['nome']}")
    todos_produtos = []

    try:
        # Acessar primeira página da categoria
        url_base = categoria['url']
        log(f"📡 Acessando: {url_base}")

        response = await page.goto(url_base, wait_until='domcontentloaded', timeout=60000)
        if response.status != 200:
            log(f"⚠️ Status HTTP: {response.status}", "WARNING")
            return []

        await page.wait_for_timeout(3000)

        # Fazer scroll para carregar produtos
        for i in range(3):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(800)

        # Detectar total de páginas
        total_paginas = await detectar_total_paginas(page)
        log(f"📄 Total de páginas detectadas: {total_paginas}")

        # Limitar páginas (segurança)
        total_paginas = min(total_paginas, max_paginas)

        # Iterar por todas as páginas
        for num_pagina in range(1, total_paginas + 1):
            try:
                # Se não for a primeira página, navegar
                if num_pagina > 1:
                    url_pagina = f"{url_base}?pagina={num_pagina}"
                    log(f"📄 Acessando página {num_pagina}/{total_paginas}: {url_pagina}")

                    await page.goto(url_pagina, wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(3000)

                    # Scroll novamente
                    for i in range(3):
                        await page.evaluate('window.scrollBy(0, window.innerHeight)')
                        await page.wait_for_timeout(800)

                # Extrair produtos da página atual
                produtos_pagina = await extrair_produtos_pagina(page, categoria['nome'])

                if produtos_pagina:
                    log(f"✅ Extraídos {len(produtos_pagina)} produtos da página {num_pagina}")

                    # Adicionar fonte (URL da página)
                    url_atual = f"{url_base}?pagina={num_pagina}" if num_pagina > 1 else url_base
                    for produto in produtos_pagina:
                        produto['fonte'] = url_atual

                    todos_produtos.extend(produtos_pagina)
                else:
                    log(f"⚠️ Nenhum produto encontrado na página {num_pagina}", "WARNING")
                    # Se não encontrou produtos, pode ter acabado a paginação
                    if num_pagina > 1:
                        break

                # Pequeno delay entre páginas
                await page.wait_for_timeout(1500)

            except Exception as e:
                log(f"❌ Erro ao processar página {num_pagina}: {str(e)}", "ERROR")
                continue

        log(f"✅ Categoria '{categoria['nome']}' concluída: {len(todos_produtos)} produtos")
        return todos_produtos

    except Exception as e:
        log(f"❌ Erro ao processar categoria '{categoria['nome']}': {str(e)}", "ERROR")
        return todos_produtos

async def scrape_mestre_parrillero(headless=True, categorias_selecionadas: List[Dict] = None) -> List[Dict]:
    """
    Faz scraping completo do site Mestre Parrillero
    Coleta TODOS os produtos de todas as categorias com paginação
    """
    log("🔥 Iniciando scraping COMPLETO da Mestre Parrilleros...")

    if categorias_selecionadas is None:
        categorias_selecionadas = CATEGORIAS

    todos_produtos = []

    async with async_playwright() as p:
        log(f"🌐 Abrindo navegador (headless={headless})...")
        browser = await p.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='pt-BR'
        )

        page = await context.new_page()

        if DEBUG:
            page.on("console", lambda msg: log(f"Browser: {msg.text}", "DEBUG"))

        try:
            # Acessar home primeiro (estratégia)
            log("📡 Acessando página inicial...")
            await page.goto('https://www.lojamestreparrillero.com.br/', wait_until='domcontentloaded', timeout=60000)
            log("✅ Página inicial carregada")
            await page.wait_for_timeout(2000)

            # Iterar por todas as categorias
            for i, categoria in enumerate(categorias_selecionadas, 1):
                log(f"\n{'='*70}")
                log(f"📂 CATEGORIA {i}/{len(categorias_selecionadas)}: {categoria['nome']}")
                log(f"{'='*70}")

                produtos_categoria = await scrape_categoria_com_paginacao(page, categoria)
                todos_produtos.extend(produtos_categoria)

                log(f"📊 Total acumulado até agora: {len(todos_produtos)} produtos")

                # Delay entre categorias
                if i < len(categorias_selecionadas):
                    await page.wait_for_timeout(2000)

            log(f"\n{'='*70}")
            log(f"✅ SCRAPING COMPLETO! Total de produtos: {len(todos_produtos)}")
            log(f"{'='*70}\n")

            # Preview de produtos únicos por categoria
            if todos_produtos and DEBUG:
                log("\n📊 RESUMO POR CATEGORIA:", "DEBUG")
                resumo = {}
                for p in todos_produtos:
                    cat = p.get('categoria', 'Sem categoria')
                    resumo[cat] = resumo.get(cat, 0) + 1

                for cat, qtd in resumo.items():
                    log(f"   {cat}: {qtd} produtos", "DEBUG")
                log("")

            return todos_produtos

        except Exception as e:
            log(f"❌ Erro durante o scraping: {str(e)}", "ERROR")

            if DEBUG:
                try:
                    html_content = await page.content()
                    with open('debug_page.html', 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    log("🔍 HTML da página salvo em: debug_page.html", "DEBUG")
                except:
                    pass

            raise
        finally:
            await browser.close()
            log("🔒 Navegador fechado")

def salvar_json(produtos, filename='produtos_parrilla.json'):
    """Salva produtos em JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(produtos, f, ensure_ascii=False, indent=2)
    log(f"💾 Dados salvos em: {filename}")

# ==================== INTEGRAÇÃO POSTGRESQL ====================

def criar_conexao_postgres():
    """Cria conexão com PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        log("✅ Conexão com PostgreSQL estabelecida")
        return conn
    except ImportError:
        log("⚠️ psycopg2 não instalado. Instale: pip install psycopg2-binary", "WARNING")
        return None
    except Exception as e:
        log(f"❌ Erro ao conectar ao PostgreSQL: {str(e)}", "ERROR")
        return None

def criar_tabela_produtos(conn):
    """Cria tabela de produtos se não existir"""
    try:
        cursor = conn.cursor()

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            produto_id VARCHAR(100),
            sku VARCHAR(100),
            nome VARCHAR(500) NOT NULL,
            preco_texto VARCHAR(50),
            preco_valor DECIMAL(10, 2),
            imagem TEXT,
            link TEXT NOT NULL,
            categoria VARCHAR(200),
            status VARCHAR(50),
            fonte TEXT,
            data_scraping TIMESTAMP,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(link)
        );

        CREATE INDEX IF NOT EXISTS idx_produto_id ON produtos(produto_id);
        CREATE INDEX IF NOT EXISTS idx_categoria ON produtos(categoria);
        CREATE INDEX IF NOT EXISTS idx_data_scraping ON produtos(data_scraping);
        """

        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()

        log("✅ Tabela 'produtos' verificada/criada com sucesso")
        return True
    except Exception as e:
        log(f"❌ Erro ao criar tabela: {str(e)}", "ERROR")
        return False

def salvar_postgres(produtos: List[Dict], conn=None) -> Dict:
    """
    Salva produtos no PostgreSQL com deduplicação
    Retorna estatísticas de inserção/atualização
    """
    if not produtos:
        log("⚠️ Nenhum produto para salvar no banco", "WARNING")
        return {'inseridos': 0, 'atualizados': 0, 'erros': 0}

    fechar_conexao = False
    if conn is None:
        conn = criar_conexao_postgres()
        if conn is None:
            return {'inseridos': 0, 'atualizados': 0, 'erros': len(produtos)}
        fechar_conexao = True

    try:
        criar_tabela_produtos(conn)

        cursor = conn.cursor()
        inseridos = 0
        atualizados = 0
        erros = 0

        upsert_sql = """
        INSERT INTO produtos (
            produto_id, sku, nome, preco_texto, preco_valor,
            imagem, link, categoria, status, fonte, data_scraping
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (link)
        DO UPDATE SET
            produto_id = EXCLUDED.produto_id,
            sku = EXCLUDED.sku,
            nome = EXCLUDED.nome,
            preco_texto = EXCLUDED.preco_texto,
            preco_valor = EXCLUDED.preco_valor,
            imagem = EXCLUDED.imagem,
            categoria = EXCLUDED.categoria,
            status = EXCLUDED.status,
            fonte = EXCLUDED.fonte,
            data_scraping = EXCLUDED.data_scraping,
            atualizado_em = CURRENT_TIMESTAMP
        RETURNING (xmax = 0) AS inserted;
        """

        for produto in produtos:
            try:
                # Converter data_scraping para datetime se for string
                data_scraping = produto.get('data_scraping')
                if isinstance(data_scraping, str):
                    data_scraping = datetime.fromisoformat(data_scraping.replace('Z', '+00:00'))

                cursor.execute(upsert_sql, (
                    produto.get('id', ''),
                    produto.get('sku', ''),
                    produto.get('nome', ''),
                    produto.get('preco_texto', ''),
                    produto.get('preco_valor'),
                    produto.get('imagem', ''),
                    produto.get('link', ''),
                    produto.get('categoria', ''),
                    produto.get('status', 'Disponível'),
                    produto.get('fonte', ''),
                    data_scraping
                ))

                result = cursor.fetchone()
                if result and result[0]:  # inserted = True
                    inseridos += 1
                else:
                    atualizados += 1

            except Exception as e:
                erros += 1
                log(f"❌ Erro ao salvar produto '{produto.get('nome', 'desconhecido')}': {str(e)}", "ERROR")
                continue

        conn.commit()
        cursor.close()

        log(f"✅ PostgreSQL: {inseridos} inseridos, {atualizados} atualizados, {erros} erros")

        return {
            'inseridos': inseridos,
            'atualizados': atualizados,
            'erros': erros
        }

    except Exception as e:
        log(f"❌ Erro ao salvar no PostgreSQL: {str(e)}", "ERROR")
        return {'inseridos': 0, 'atualizados': 0, 'erros': len(produtos)}
    finally:
        if fechar_conexao and conn:
            conn.close()
            log("🔒 Conexão com PostgreSQL fechada")

'''
def salvar_excel(produtos, filename='produtos_parrilla.xlsx'):
    """Salva produtos em Excel"""
    try:
        import pandas as pd
        df = pd.DataFrame(produtos)
        df.to_excel(filename, index=False, engine='openpyxl')
        log(f"📊 Planilha Excel salva em: {filename}")
    except ImportError:
        log("⚠️ pandas/openpyxl não instalado. Pulando Excel.", "WARNING")
    except Exception as e:
        log(f"❌ Erro ao salvar Excel: {str(e)}", "ERROR")
'''

async def scrape_com_retry(headless=True, max_tentativas=MAX_RETRIES) -> List[Dict]:
    """Executa scraping com retry logic"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            log(f"🔄 Tentativa {tentativa}/{max_tentativas}")
            produtos = await scrape_mestre_parrillero(headless=headless)

            if produtos:
                log(f"✅ Scraping bem-sucedido na tentativa {tentativa}")
                return produtos
            else:
                log(f"⚠️ Nenhum produto encontrado na tentativa {tentativa}", "WARNING")

                if tentativa < max_tentativas:
                    delay = 2 ** tentativa  # Backoff exponencial: 2s, 4s, 8s
                    log(f"⏳ Aguardando {delay}s antes da próxima tentativa...")
                    await asyncio.sleep(delay)

        except Exception as e:
            log(f"❌ Erro na tentativa {tentativa}: {str(e)}", "ERROR")

            if tentativa < max_tentativas:
                delay = 2 ** tentativa
                log(f"⏳ Aguardando {delay}s antes de tentar novamente...")
                await asyncio.sleep(delay)
            else:
                log(f"❌ Todas as {max_tentativas} tentativas falharam", "ERROR")
                raise

    return []

async def main():
    """Função principal com suporte completo"""
    inicio = datetime.now()

    try:
        log("="*70)
        log("🔥 SCRAPER MESTRE PARRILLERO - VERSÃO COMPLETA", "INFO")
        log("="*70)
        log(f"📅 Início: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"🗂️  Categorias: {len(CATEGORIAS)}")
        log(f"💾 Banco de dados: PostgreSQL")
        log("="*70 + "\n")

        # Perguntar se quer ver o navegador
        if DEBUG and sys.stdin.isatty():
            resposta = input("\n🤔 Quer ver o navegador funcionando? (s/n): ").lower()
            headless = resposta != 's'
        else:
            headless = True

        # Executar scraping com retry
        produtos = await scrape_com_retry(headless=headless)

        if produtos:
            # Salvar em JSON (backup)
            salvar_json(produtos)

            # Salvar no PostgreSQL
            log("\n💾 Salvando no PostgreSQL...")
            stats = salvar_postgres(produtos)

            # Resumo final
            fim = datetime.now()
            duracao = (fim - inicio).total_seconds()

            log("\n" + "="*70)
            log("📊 RESUMO FINAL", "SUCCESS")
            log("="*70)
            log(f"✅ Total de produtos: {len(produtos)}")
            log(f"📁 Categorias processadas: {len(CATEGORIAS)}")
            log(f"⏱️  Duração: {duracao:.2f} segundos")
            log("\n💾 Arquivos salvos:")
            log(f"   - produtos_parrilla.json ({len(produtos)} produtos)")

            if stats:
                log("\n🗄️  PostgreSQL:")
                log(f"   - Inseridos: {stats.get('inseridos', 0)}")
                log(f"   - Atualizados: {stats.get('atualizados', 0)}")
                log(f"   - Erros: {stats.get('erros', 0)}")

            # Resumo por categoria
            log("\n📂 Produtos por categoria:")
            categorias_resumo = {}
            for p in produtos:
                cat = p.get('categoria', 'Sem categoria')
                categorias_resumo[cat] = categorias_resumo.get(cat, 0) + 1

            for cat, qtd in sorted(categorias_resumo.items()):
                log(f"   - {cat}: {qtd} produtos")

            log("="*70 + "\n")

            # Output para n8n
            print("__N8N_OUTPUT_START__")
            print(json.dumps({
                'produtos': produtos,
                'total': len(produtos),
                'categorias': categorias_resumo,
                'stats_db': stats,
                'duracao_segundos': duracao,
                'timestamp': datetime.now().isoformat()
            }, ensure_ascii=False))
            print("__N8N_OUTPUT_END__")

            return produtos
        else:
            log("⚠️ Nenhum produto foi encontrado!", "WARNING")
            return []

    except Exception as e:
        log(f"❌ Erro fatal: {str(e)}", "ERROR")
        if DEBUG:
            import traceback
            log("\n📋 Stack trace completo:", "DEBUG")
            traceback.print_exc()
        return []

if __name__ == "__main__":
    asyncio.run(main())