import os
import base64
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import gdown

# =========================
# CONFIGURAÇÕES
# =========================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

URL_EXCEL = "https://drive.google.com/uc?id=1SBbrWnhXnS9azkEOJuyjL4BuI_LIT00E"
ARQUIVO_LOCAL = "arquivo_temp.xlsx"
LOGO_LOCAL = "logo_panco.png"

st.set_page_config(
    page_title="Agente Panquinho",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# LOGO
# =========================

def carregar_logo_base64(caminho_logo):
    if os.path.exists(caminho_logo):
        with open(caminho_logo, "rb") as arquivo:
            return base64.b64encode(arquivo.read()).decode()
    return None

logo_base64 = carregar_logo_base64(LOGO_LOCAL)

logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo">' if logo_base64 else ""

# =========================
# CSS / HEADER
# =========================

st.markdown("""
<style>
.header-fixo {
    position: fixed;
    top: 48px;
    left: 0;
    width: 100%;
    height: 72px;
    background-color: #D60000;
    color: white;
    padding: 0 28px;
    z-index: 9999;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0px 2px 10px rgba(0,0,0,0.25);
}

.logo {
    height: 44px;
    background: white;
    border-radius: 8px;
    padding: 4px;
}

.header-title {
    font-size: 28px;
    font-weight: 800;
    margin: 0;
}

.block-container {
    padding-top: 150px !important;
}

[data-testid="stSidebar"] {
    padding-top: 120px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="header-fixo">
    {logo_html}
    <h1 class="header-title">Agente Panquinho</h1>
</div>
""", unsafe_allow_html=True)

# =========================
# CARREGAR PLANILHA (MULTI ABAS)
# =========================

@st.cache_data
def carregar_planilha():
    if not os.path.exists(ARQUIVO_LOCAL) or os.path.getsize(ARQUIVO_LOCAL) < 1000:
        gdown.download(URL_EXCEL, ARQUIVO_LOCAL, quiet=False)

    dfs = pd.read_excel(ARQUIVO_LOCAL, sheet_name=None)

    # Padronizar datas
    for nome_aba, df in dfs.items():
        for coluna in df.columns:
            nome_coluna = str(coluna).lower()

            if "data" in nome_coluna or "date" in nome_coluna:
                df[coluna] = pd.to_datetime(df[coluna], dayfirst=True, errors="coerce")

        dfs[nome_aba] = df

    return dfs

dfs = carregar_planilha()

# Aba padrão (opcional)
df = list(dfs.values())[0]

# =========================
# SIDEBAR
# =========================

st.sidebar.header("📊 Abas carregadas")

for nome, df_temp in dfs.items():
    st.sidebar.write(f"📄 {nome} → {len(df_temp)} linhas")

with st.sidebar.expander("Ver estrutura"):
    for nome, df_temp in dfs.items():
        st.write(f"### {nome}")
        st.write(list(df_temp.columns))

# =========================
# HISTÓRICO
# =========================

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# =========================
# GERAR CÓDIGO (MULTI ABAS)
# =========================

def gerar_codigo(pergunta):
    estrutura = ""

    for nome, df_temp in dfs.items():
        estrutura += f"\nAba: {nome}\nColunas: {list(df_temp.columns)}\n"

    prompt = f"""
Você é um analista de dados sênior.

Você deve responder perguntas usando múltiplas abas.

As abas estão no dicionário dfs:
dfs["nome_da_aba"]

Gere APENAS código Python.

Regras:
- Use dfs["nome_da_aba"]
- Não explique nada
- Não use markdown
- O resultado deve ficar na variável resultado
- Não use import
- Não use print
- Não use arquivos

Estrutura:
{estrutura}

Pergunta:
{pergunta}
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return resposta.output_text.strip()

# =========================
# SEGURANÇA
# =========================

def validar_codigo(codigo):
    proibidos = [
        "import", "open(", "exec(", "eval(",
        "__", "os.", "sys.", "subprocess",
        "read_excel", "to_excel", "read_csv"
    ]

    for termo in proibidos:
        if termo in codigo.lower():
            raise ValueError(f"Código bloqueado: {termo}")

def executar_codigo(codigo):
    validar_codigo(codigo)

    ambiente = {
        "dfs": {k: v.copy() for k, v in dfs.items()},
        "pd": pd,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "round": round
    }

    exec(codigo, {"__builtins__": {}}, ambiente)

    if "resultado" not in ambiente:
        raise ValueError("Código não gerou 'resultado'")

    return ambiente["resultado"]

# =========================
# RESPOSTA FINAL
# =========================

def gerar_resposta(pergunta, resultado):
    if isinstance(resultado, pd.DataFrame):
        texto = resultado.head(50).to_string()
    elif isinstance(resultado, pd.Series):
        texto = resultado.to_string()
    else:
        texto = str(resultado)

    prompt = f"""
Você é um analista de dados da Panco.

Responda de forma clara e objetiva.

Regras:
- Não invente dados
- Use R$ para valores monetários
- Se não houver dados, informe
- Sempre dê uma recomendação no final

Pergunta:
{pergunta}

Resultado:
{texto}
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return resposta.output_text.strip()

# =========================
# CHAT
# =========================

pergunta = st.chat_input("Pergunte sobre os dados...")

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})

    with st.chat_message("user"):
        st.write(pergunta)

    with st.chat_message("assistant"):
        try:
            codigo = gerar_codigo(pergunta)
            resultado = executar_codigo(codigo)
            resposta = gerar_resposta(pergunta, resultado)

            st.write(resposta)

            with st.expander("🔍 Ver código gerado"):
                st.code(codigo, language="python")

            if isinstance(resultado, pd.DataFrame):
                st.dataframe(resultado)
            elif isinstance(resultado, pd.Series):
                st.dataframe(resultado.reset_index())
            else:
                st.write(resultado)

        except Exception as e:
            st.error(f"Erro: {e}")
            resposta = f"Erro ao processar: {e}"

    st.session_state.mensagens.append({"role": "assistant", "content": resposta})