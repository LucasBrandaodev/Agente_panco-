import os
import base64
import json
import traceback
import difflib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import gdown

# =========================
# CONFIGURAÇÕES
# =========================

load_dotenv()

try:
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY não encontrada. Configure no arquivo .env ou no Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

URL_EXCEL = "https://drive.google.com/uc?id=1SBbrWnhXnS9azkEOJuyjL4BuI_LIT00E"
ARQUIVO_LOCAL = "arquivo_temp.xlsx"
LOGO_LOCAL = "logo_panco.png"
MEMORIA_LOCAL = "memoria_agente.json"

st.set_page_config(
    page_title="Agente Panquinho",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# MEMÓRIA PROGRESSIVA
# =========================

def carregar_memoria():
    if os.path.exists(MEMORIA_LOCAL):
        try:
            with open(MEMORIA_LOCAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"aprendizados": [], "exemplos": []}

    return {"aprendizados": [], "exemplos": []}


def salvar_memoria(memoria):
    with open(MEMORIA_LOCAL, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


memoria = carregar_memoria()

# =========================
# IMAGEM
# =========================

def carregar_imagem_base64(caminho):
    if os.path.exists(caminho):
        with open(caminho, "rb") as arquivo:
            return base64.b64encode(arquivo.read()).decode()
    return None


logo_base64 = carregar_imagem_base64(LOGO_LOCAL)

logo_html = ""
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo">'

# =========================
# CSS
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
    font-size: 38px;
    font-weight: 900;
    margin: 0;
}

.mascote {
    position: fixed;
    right: 22px;
    top: 78px;
    height: 95px;
    z-index: 10000;
    pointer-events: none;
    filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.3));
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

if logo_base64:
    st.markdown(f"""
    <img src="data:image/png;base64,{logo_base64}" class="mascote">
    """, unsafe_allow_html=True)

# =========================
# CARREGAR PLANILHA
# =========================

@st.cache_data
def carregar_planilha():
    if not os.path.exists(ARQUIVO_LOCAL) or os.path.getsize(ARQUIVO_LOCAL) < 1000:
        gdown.download(URL_EXCEL, ARQUIVO_LOCAL, quiet=False)

    dfs = pd.read_excel(ARQUIVO_LOCAL, sheet_name=None)

    for nome_aba, df in dfs.items():
        df.columns = [str(col).strip() for col in df.columns]

        for coluna in df.columns:
            nome_coluna = str(coluna).lower()

            if "data" in nome_coluna or "date" in nome_coluna:
                df[coluna] = pd.to_datetime(df[coluna], dayfirst=True, errors="coerce")

        dfs[nome_aba] = df

    return dfs


try:
    dfs = carregar_planilha()
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

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

with st.sidebar.expander("🧠 Memória do agente"):
    st.write(f"Aprendizados: {len(memoria.get('aprendizados', []))}")
    st.write(f"Exemplos salvos: {len(memoria.get('exemplos', []))}")

# =========================
# HISTÓRICO
# =========================

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# =========================
# GERAR CÓDIGO
# =========================

def gerar_codigo(pergunta, erro_anterior=None, codigo_anterior=None):
    estrutura = ""

    for nome, df_temp in dfs.items():
        estrutura += f"""
Aba: {nome}
Colunas: {list(df_temp.columns)}
Linhas: {len(df_temp)}
Amostra:
{df_temp.head(3).to_string(index=False)}
"""

    aprendizados = "\n".join(memoria.get("aprendizados", [])[-10:])
    exemplos = "\n".join(
        [
            f"Pergunta: {ex.get('pergunta')}\nCódigo usado:\n{ex.get('codigo')}"
            for ex in memoria.get("exemplos", [])[-5:]
        ]
    )

    correcao = ""
    if erro_anterior:
        correcao = f"""
O código anterior falhou.

Código anterior:
{codigo_anterior}

Erro:
{erro_anterior}

Corrija o código e gere uma nova versão.
"""

    prompt = f"""
Você é um analista de dados sênior.

Você deve gerar código Python para responder perguntas usando o dicionário dfs.

As abas estão em:
dfs["nome_da_aba"]

Gere APENAS código Python executável.

Regras obrigatórias:
- Use somente os dados existentes em dfs
- Não invente dados
- O resultado final deve ficar obrigatoriamente na variável resultado
- Pode usar pandas como pd
- Pode usar funções Python normais
- Pode criar variáveis auxiliares
- Pode usar loops, filtros, groupby, sort_values, merge, pivot_table
- Não use arquivos externos
- Não use input
- Não use print
- Para datas como hoje, use pd.Timestamp.today().normalize()
- Se o usuário citar uma aba com nome aproximado, use a aba mais parecida
- Se não encontrar coluna necessária, resultado = "Não encontrei a coluna necessária para responder."
- Se não houver dados, resultado = "Não encontrei dados para responder."

Aprendizados anteriores:
{aprendizados}

Exemplos anteriores de sucesso:
{exemplos}

Estrutura da planilha:
{estrutura}

{correcao}

Pergunta do usuário:
{pergunta}
"""

    resposta = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    codigo = resposta.output_text.strip()
    codigo = codigo.replace("```python", "").replace("```", "").strip()

    return codigo

# =========================
# EXECUTAR CÓDIGO SEM BLOQUEIOS
# =========================

def executar_codigo(codigo):
    ambiente = {
        "dfs": {k: v.copy() for k, v in dfs.items()},
        "pd": pd,
        "difflib": difflib,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "round": round,
        "str": str,
        "int": int,
        "float": float,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sorted": sorted,
        "abs": abs,
        "enumerate": enumerate,
        "range": range,
        "all": all,
        "any": any,
        "zip": zip
    }

    exec(codigo, ambiente, ambiente)

    if "resultado" not in ambiente:
        return "Sem resultado"

    return ambiente["resultado"]

# =========================
# RESPOSTA FINAL COM RECOMENDAÇÃO
# =========================

def gerar_resposta(pergunta, resultado):
    if isinstance(resultado, pd.DataFrame):
        texto = resultado.head(80).to_string(index=False)
    elif isinstance(resultado, pd.Series):
        texto = resultado.to_string()
    else:
        texto = str(resultado)

    prompt = f"""
Você é o Agente Panquinho, um analista de dados sênior da Panco.

Responda sempre em português do Brasil.

Sua resposta deve seguir esta estrutura:

📊 Resposta direta
Responda objetivamente a pergunta do usuário.

📈 Interpretação
Explique o que o resultado significa para o negócio.

💡 Insight
Mostre uma oportunidade, risco, tendência ou ponto de atenção.

🚀 Recomendação excelente
Dê uma recomendação prática, forte e acionável.
A recomendação deve ajudar na tomada de decisão comercial, operacional ou estratégica.

Regras:
- Não invente dados
- Use apenas o resultado recebido
- Se houver valores monetários, use R$
- Se não houver dados, explique claramente
- A recomendação deve ser específica, não genérica
- Não diga que consultou código
- Não cite DataFrame, Series ou Python

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
# APRENDER COM RESULTADO
# =========================

def atualizar_memoria(pergunta, codigo, resultado, resposta):
    try:
        memoria.setdefault("exemplos", [])
        memoria.setdefault("aprendizados", [])

        memoria["exemplos"].append({
            "pergunta": pergunta,
            "codigo": codigo,
            "resumo_resultado": str(resultado)[:1000]
        })

        prompt = f"""
Extraia um aprendizado curto para melhorar respostas futuras deste agente.

Pergunta:
{pergunta}

Resultado:
{str(resultado)[:1500]}

Resposta:
{resposta[:1500]}

Retorne apenas uma frase curta.
"""

        r = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        aprendizado = r.output_text.strip()

        if aprendizado:
            memoria["aprendizados"].append(aprendizado)

        memoria["exemplos"] = memoria["exemplos"][-30:]
        memoria["aprendizados"] = memoria["aprendizados"][-50:]

        salvar_memoria(memoria)

    except Exception:
        pass

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

            try:
                resultado = executar_codigo(codigo)

            except Exception as erro:
                codigo_corrigido = gerar_codigo(
                    pergunta,
                    erro_anterior=traceback.format_exc(),
                    codigo_anterior=codigo
                )

                codigo = codigo_corrigido
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

            atualizar_memoria(pergunta, codigo, resultado, resposta)

        except Exception as e:
            resposta = f"Erro ao processar: {e}"
            st.error(resposta)

    st.session_state.mensagens.append({"role": "assistant", "content": resposta})