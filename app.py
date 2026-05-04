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
ABA_EXCEL = "BD"
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

if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo">'
else:
    logo_html = ""

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
    line-height: 1;
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
# CARREGAR PLANILHA
# =========================

@st.cache_data
def carregar_planilha():
    if not os.path.exists(ARQUIVO_LOCAL) or os.path.getsize(ARQUIVO_LOCAL) < 1000:
        gdown.download(URL_EXCEL, ARQUIVO_LOCAL, quiet=False)

    df = pd.read_excel(ARQUIVO_LOCAL, sheet_name=ABA_EXCEL)

    for coluna in df.columns:
        nome_coluna = str(coluna).lower()

        if "data" in nome_coluna or coluna == "Cód C.Fornec.":
            df[coluna] = pd.to_datetime(df[coluna], dayfirst=True, errors="coerce")

    return df

df = carregar_planilha()

# =========================
# SIDEBAR
# =========================

st.sidebar.header("Base carregada")
st.sidebar.write("Linhas:", len(df))
st.sidebar.write("Colunas:", len(df.columns))

with st.sidebar.expander("Ver colunas"):
    st.write(list(df.columns))

# =========================
# HISTÓRICO
# =========================

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# =========================
# GERAR CÓDIGO PANDAS
# =========================

def gerar_codigo(pergunta):
    colunas = list(df.columns)
    amostra = df.head(15).to_string()

    prompt = f"""
Você é um analista de dados sênior.

Você deve responder perguntas sobre uma planilha Excel usando pandas.

Gere APENAS código Python.
Não explique.
Não use markdown.
Não use ```.

Regras obrigatórias:
- O dataframe já existe e se chama df.
- Use somente os dados do dataframe df.
- Use somente colunas existentes.
- O resultado final deve ser salvo na variável resultado.
- Não leia arquivos.
- Não importe bibliotecas.
- Não use print.
- Não use input.
- Não use exec, eval, open, os, sys ou subprocess.
- Se a pergunta envolver hoje, use pd.Timestamp.today().
- Se a pergunta envolver ontem, use pd.Timestamp.today() - pd.Timedelta(days=1).
- Se houver coluna de data, compare usando .dt.date.
- Para YTD, considere do primeiro dia do ano atual até hoje.
- Para MTD, considere do primeiro dia do mês atual até hoje.
- Para ranking, agrupe e ordene do maior para o menor.
- Para faturamento, venda ou receita, use a coluna numérica mais relacionada a valor, venda líquida, faturamento, receita ou total.

Colunas disponíveis:
{colunas}

Amostra da base:
{amostra}

Pergunta do usuário:
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
    bloqueados = [
        "import ",
        "open(",
        "exec(",
        "eval(",
        "__",
        "os.",
        "sys.",
        "subprocess",
        "shutil",
        "socket",
        "requests",
        "read_excel",
        "read_csv",
        "to_excel",
        "to_csv"
    ]

    codigo_lower = codigo.lower()

    for termo in bloqueados:
        if termo in codigo_lower:
            raise ValueError(f"Código bloqueado por segurança: {termo}")

def executar_codigo(codigo):
    validar_codigo(codigo)

    ambiente = {
        "df": df.copy(),
        "pd": pd,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "round": round,
        "abs": abs,
        "float": float,
        "int": int,
        "str": str
    }

    exec(codigo, {"__builtins__": {}}, ambiente)

    if "resultado" not in ambiente:
        raise ValueError("O código não gerou a variável resultado.")

    return ambiente["resultado"]

# =========================
# GERAR RESPOSTA FINAL
# =========================

def gerar_resposta(pergunta, resultado):
    if isinstance(resultado, pd.DataFrame):
        texto_resultado = resultado.head(50).to_string()
    elif isinstance(resultado, pd.Series):
        texto_resultado = resultado.to_string()
    else:
        texto_resultado = str(resultado)

    prompt = f"""
Você é um analista de dados sênior da Panco.

Responda de forma clara, objetiva e profissional.

Regras:
- responda sempre baseado na planilha .
- Nunca invente valores.
- Se o resultado estiver vazio, informe que não foram encontrados dados.
- Formate valores monetários em R$ quando fizer sentido.
- Seja direto.
- traga sempre uma recomendação ao final de cada resultado

Pergunta do usuário:
{pergunta}

Resultado calculado:
{texto_resultado}
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return resposta.output_text.strip()

# =========================
# CHAT
# =========================

pergunta = st.chat_input("Digite sua pergunta sobre a planilha...")

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})

    with st.chat_message("user"):
        st.write(pergunta)

    with st.chat_message("assistant"):
        try:
            codigo = gerar_codigo(pergunta)
            resultado = executar_codigo(codigo)
            resposta_final = gerar_resposta(pergunta, resultado)

            st.write(resposta_final)

            with st.expander("Ver cálculo executado"):
                st.code(codigo, language="python")

            if isinstance(resultado, pd.DataFrame):
                st.dataframe(resultado)
            elif isinstance(resultado, pd.Series):
                st.dataframe(resultado.reset_index())
            else:
                st.write(resultado)

        except Exception as erro:
            resposta_final = f"Não consegui calcular com segurança. Erro: {erro}"
            st.error(resposta_final)

    st.session_state.mensagens.append(
        {"role": "assistant", "content": resposta_final}
    )