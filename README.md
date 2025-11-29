# 🔥 Scraper Mestre Parrillero - Versão Completa

Scraper completo para extrair **TODOS** os produtos do site [Loja Mestre Parrillero](https://www.lojamestreparrillero.com.br/) com paginação automática, múltiplas categorias e integração com PostgreSQL.

## ✨ Funcionalidades

- ✅ **Paginação automática**: Detecta e extrai produtos de todas as páginas
- ✅ **7 categorias completas**: Coleta de todas as categorias do site
- ✅ **100+ produtos**: Extração de todos os produtos disponíveis
- ✅ **Integração PostgreSQL**: Salvamento automático com deduplicação
- ✅ **Limpeza de dados**: Preços normalizados e valores numéricos
- ✅ **Retry logic**: Retentar automaticamente em caso de erro
- ✅ **Backup JSON**: Salva também em arquivo local
- ✅ **Compatível com n8n**: Output formatado para automação

## 📋 Categorias Coletadas

1. Churrasqueiras e Parrillas
2. Bancada de Embutir
3. Churrasqueiras para Alvenaria
4. Bancada
5. Portátil Externa
6. Sem Fumaça
7. Acessórios

## 🚀 Instalação

### 1. Clonar ou baixar o projeto

```bash
cd scraper-mestre-parrillero
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Instalar navegadores do Playwright

```bash
playwright install chromium
```

### 4. Configurar banco de dados (opcional)

Copie o arquivo `.env.example` para `.env` e configure suas credenciais:

```bash
cp .env.example .env
```

Edite o arquivo `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mestre_parrillero
DB_USER=postgres
DB_PASSWORD=sua_senha
```

### 5. Criar banco de dados PostgreSQL

```sql
CREATE DATABASE mestre_parrillero;
```

A tabela `produtos` será criada automaticamente na primeira execução.

## 📊 Schema da Tabela PostgreSQL

```sql
CREATE TABLE produtos (
    id SERIAL PRIMARY KEY,
    produto_id VARCHAR(100),
    sku VARCHAR(100),
    nome VARCHAR(500) NOT NULL,
    preco_texto VARCHAR(50),
    preco_valor DECIMAL(10, 2),
    imagem TEXT,
    link TEXT NOT NULL UNIQUE,
    categoria VARCHAR(200),
    status VARCHAR(50),
    fonte TEXT,
    data_scraping TIMESTAMP,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Deduplicação**: Produtos são identificados pelo `link` (URL). Se o produto já existir, ele será atualizado.

## 🎯 Como Usar

### Execução simples

```bash
python scraper.py
```

### Modo headless (sem interface)

Por padrão, o scraper roda em modo headless. Para ver o navegador funcionando, responda "s" quando perguntado.

### Output

O scraper gera:

1. **`produtos_parrilla.json`**: Backup local com todos os produtos
2. **Banco PostgreSQL**: Produtos salvos com deduplicação
3. **Output n8n**: JSON formatado entre `__N8N_OUTPUT_START__` e `__N8N_OUTPUT_END__`

## 📦 Estrutura dos Dados

Cada produto contém:

```json
{
  "id": "123",
  "sku": "MP-001",
  "nome": "Churrasqueira Portátil",
  "preco_texto": "R$ 1.510,40",
  "preco_valor": 1510.40,
  "imagem": "https://...",
  "link": "https://...",
  "categoria": "Churrasqueiras e Parrillas",
  "status": "Disponível",
  "fonte": "https://...",
  "data_scraping": "2025-01-27T10:30:00"
}
```

## 🔧 Configurações Avançadas

### Variáveis de ambiente

Você pode configurar via `.env` ou variáveis de ambiente:

- `DB_HOST`: Host do PostgreSQL (padrão: localhost)
- `DB_PORT`: Porta do PostgreSQL (padrão: 5432)
- `DB_NAME`: Nome do banco (padrão: mestre_parrillero)
- `DB_USER`: Usuário do banco (padrão: postgres)
- `DB_PASSWORD`: Senha do banco (padrão: postgres)

### Ajustes no código

No arquivo `scraper.py`, você pode modificar:

```python
DEBUG = True  # Logs detalhados
MAX_RETRIES = 3  # Número de tentativas
TIMEOUT = 30000  # Timeout em milissegundos
```

### Selecionar categorias específicas

Para coletar apenas algumas categorias, edite a lista `CATEGORIAS` no arquivo `scraper.py`.

## 🔄 Integração com n8n

### 1. Criar Node "Execute Command"

No n8n, adicione um node "Execute Command" com:

```bash
cd /caminho/para/scraper-mestre-parrillero && python scraper.py
```

### 2. Processar output

O JSON será retornado entre os marcadores:
- `__N8N_OUTPUT_START__`
- `__N8N_OUTPUT_END__`

Use um node "Code" para extrair:

```javascript
const output = $input.first().json.stdout;
const match = output.match(/__N8N_OUTPUT_START__([\s\S]*?)__N8N_OUTPUT_END__/);
if (match) {
  const data = JSON.parse(match[1]);
  return [{ json: data }];
}
```

### 3. Agendar execução

Configure um node "Schedule Trigger" para executar periodicamente (ex: diariamente).

## 📈 Monitoramento

O scraper fornece logs detalhados:

```
[2025-01-27 10:30:00] [INFO] 🔥 Iniciando scraping COMPLETO...
[2025-01-27 10:30:05] [INFO] 📂 CATEGORIA 1/7: Churrasqueiras e Parrillas
[2025-01-27 10:30:10] [INFO] ✅ Extraídos 30 produtos da página 1
[2025-01-27 10:30:15] [INFO] ✅ Extraídos 28 produtos da página 2
[2025-01-27 10:30:20] [SUCCESS] ✅ Categoria concluída: 58 produtos
...
[2025-01-27 10:35:00] [SUCCESS] 📊 RESUMO FINAL
[2025-01-27 10:35:00] [SUCCESS] ✅ Total de produtos: 125
```

## 🐛 Troubleshooting

### Erro: "psycopg2 não instalado"

```bash
pip install psycopg2-binary
```

### Erro: "Conexão ao PostgreSQL falhou"

Verifique:
1. PostgreSQL está rodando
2. Credenciais no `.env` estão corretas
3. Banco de dados foi criado

### Erro: "Nenhum produto encontrado"

Verifique:
1. Site está acessível
2. Navegador Playwright foi instalado: `playwright install chromium`
3. Tente rodar com `DEBUG = True` e veja os screenshots gerados

### Produtos duplicados

O sistema usa o campo `link` (URL) como chave única. Produtos com o mesmo link serão atualizados, não duplicados.

## 📝 Licença

Projeto de uso pessoal para automação de catálogo de produtos.

## 🤝 Suporte

Para dúvidas ou problemas, verifique:
1. Logs do scraper (modo DEBUG)
2. Screenshots gerados em caso de erro
3. Arquivo `debug_page.html` (gerado em caso de falha)

## 🔮 Próximas melhorias possíveis

- [ ] Extração de descrição completa dos produtos
- [ ] Captura de especificações técnicas
- [ ] Monitoramento de mudanças de preço
- [ ] Alertas por email/webhook
- [ ] API REST para consulta dos produtos
- [ ] Dashboard de visualização

---

**Versão**: 2.0 (Completa)
**Data**: 27/01/2025
**Autor**: Gabriel Sezaltino
