import ctypes
import io
import json
import os
import re
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pypdf import PdfReader


load_dotenv()
requests.packages.urllib3.disable_warnings()


URL_DIARIO = "https://diariooficial.vilavelha.es.gov.br/"
TARGET_PHRASES = ("agente de farmacia", "concurso", "processo seletivo")
STATE_VERSION = 3
MONITOR_MODE = "latest_only"
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 8

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_STATE = os.path.join(BASE_DIR, "ultimo_status.txt")
FILE_LOG = os.path.join(BASE_DIR, "registro")


def registrar_log(mensagem):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(FILE_LOG, "a", encoding="utf-8") as arquivo:
        arquivo.write(f"[{timestamp}] {mensagem}\n")
    print(f"[{timestamp}] {mensagem}")


def normalizar_texto(texto):
    texto = texto.replace("-\n", "")
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def resumir_texto(texto, termo, janela=180):
    indice = texto.find(termo)
    if indice == -1:
        return ""
    inicio = max(0, indice - janela)
    fim = min(len(texto), indice + len(termo) + janela)
    return texto[inicio:fim].strip()


def executar_com_retentativas(sessao, metodo, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            return sessao.request(metodo, url, **kwargs)
        except requests.RequestException as erro:
            if tentativa >= MAX_RETRIES:
                raise
            registrar_log(
                f"Falha na tentativa {tentativa}/{MAX_RETRIES} ao acessar o Diario Oficial: {erro}. Retentando em {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)


def obter_pagina_inicial(sessao):
    try:
        resposta = executar_com_retentativas(sessao, "GET", URL_DIARIO, verify=False)
        resposta.raise_for_status()
        return BeautifulSoup(resposta.text, "html.parser")
    except requests.RequestException as erro:
        registrar_log(f"Diario Oficial indisponivel no momento: {erro}")
        return None


def obter_campos_ocultos(soup):
    return {
        "__VIEWSTATE": soup.select_one("#__VIEWSTATE")["value"],
        "__VIEWSTATEGENERATOR": soup.select_one("#__VIEWSTATEGENERATOR")["value"],
        "__EVENTVALIDATION": soup.select_one("#__EVENTVALIDATION")["value"],
    }


def obter_ultima_edicao(sessao):
    soup = obter_pagina_inicial(sessao)
    if soup is None:
        return None, None

    titulo = ""
    card = soup.select_one("#ctl00_cpConteudo_gvDocumentos [id$='lblNomeArquivo']")
    if card:
        titulo = card.get_text(" ", strip=True)
    if not titulo:
        titulo = "Ultima edicao do Diario Oficial"

    payload = obter_campos_ocultos(soup)
    payload.update(
        {
            "__EVENTTARGET": "ctl00$cpConteudo$ibDownloadLastDIO",
            "__EVENTARGUMENT": "",
        }
    )

    try:
        resposta = executar_com_retentativas(sessao, "POST", URL_DIARIO, data=payload, verify=False)
        resposta.raise_for_status()
        if "application/pdf" not in resposta.headers.get("content-type", "").lower():
            return titulo, None
        return titulo, resposta.content
    except requests.RequestException as erro:
        registrar_log(f"Falha ao baixar a ultima edicao: {erro}")
        return titulo, None


def extrair_marcacoes_pdf(pdf_bytes):
    leitor = PdfReader(io.BytesIO(pdf_bytes))
    paginas_encontradas = []
    trechos = []
    has_agente = False
    has_concurso = False
    has_processo = False

    for indice, pagina in enumerate(leitor.pages, start=1):
        texto = normalizar_texto(pagina.extract_text() or "")
        if not texto:
            continue

        achou_pagina = False
        for termo in TARGET_PHRASES:
            if termo in texto:
                achou_pagina = True
                if termo == "agente de farmacia":
                    has_agente = True
                elif termo == "concurso":
                    has_concurso = True
                elif termo == "processo seletivo":
                    has_processo = True
                trecho = resumir_texto(texto, termo)
                if trecho:
                    trechos.append(f"p{indice}: {trecho}")
        if achou_pagina:
            paginas_encontradas.append(indice)
        if has_agente and has_concurso and has_processo:
            break

    return {
        "pages": paginas_encontradas,
        "snippets": trechos[:3],
        "has_agente": has_agente,
        "has_concurso": has_concurso,
        "has_processo": has_processo,
    }


def carregar_estado():
    if not os.path.exists(FILE_STATE):
        return None

    try:
        with open(FILE_STATE, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        return None


def salvar_estado(dados):
    with open(FILE_STATE, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def montar_assinatura(matches):
    resumo = []
    for item in matches:
        resumo.append(
            {
                "title": item["title"],
                "pages": item["pages"],
                "has_agente": item["has_agente"],
                "has_concurso": item["has_concurso"],
                "has_processo": item["has_processo"],
            }
        )
    return json.dumps(resumo, ensure_ascii=False, sort_keys=True)


def formatar_alerta(matches):
    linhas = ["ALERTA: encontrei publicacao relevante no ultimo Diario Oficial de Vila Velha."]
    for item in matches[:3]:
        linhas.append("")
        linhas.append(f"- {item['title']}")
        linhas.append(f"  paginas: {', '.join(str(p) for p in item['pages'])}")
        if item["snippets"]:
            linhas.append(f"  trecho: {item['snippets'][0][:240]}")
    return "\n".join(linhas)


def enviar_telegram(msg):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=15)
    except Exception as erro:
        registrar_log(f"Erro ao ligar ao Telegram: {erro}")


def monitorar():
    os.makedirs(BASE_DIR, exist_ok=True)

    sessao = requests.Session()
    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }
    )

    try:
        registrar_log("Acessando o ultimo Diario Oficial publico...")
        titulo_edicao, pdf_bytes = obter_ultima_edicao(sessao)
        if not pdf_bytes:
            registrar_log("Monitor encerrado sem nova leitura: diario indisponivel ou PDF nao retornado.")
            return

        registrar_log(f"Ultima edicao carregada: {titulo_edicao}")
        marcacoes = extrair_marcacoes_pdf(pdf_bytes)
        match = {
            "title": titulo_edicao,
            "pages": marcacoes["pages"],
            "snippets": marcacoes["snippets"],
            "has_agente": marcacoes["has_agente"],
            "has_concurso": marcacoes["has_concurso"],
            "has_processo": marcacoes["has_processo"],
        }
        matches = [match]

        resumo_kw = (
            f"agente de farmacia={'sim' if marcacoes['has_agente'] else 'nao'}, "
            f"concurso={'sim' if marcacoes['has_concurso'] else 'nao'}, "
            f"processo seletivo={'sim' if marcacoes['has_processo'] else 'nao'}"
        )
        registrar_log(f"Resumo da ultima edicao: {resumo_kw}")
        if marcacoes["snippets"]:
            registrar_log(f"Trecho encontrado: {marcacoes['snippets'][0][:240]}")

        novo_estado = {
            "mode": MONITOR_MODE,
            "version": STATE_VERSION,
            "source": URL_DIARIO,
            "edition": titulo_edicao,
            "signature": montar_assinatura(matches),
            "matches": matches,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        estado_anterior = carregar_estado()
        estado_valido = bool(
            estado_anterior
            and estado_anterior.get("source") == URL_DIARIO
            and estado_anterior.get("mode") == MONITOR_MODE
            and estado_anterior.get("version") == STATE_VERSION
        )

        if not estado_valido:
            salvar_estado(novo_estado)
            registrar_log("Estado inicial gravado para o ultimo diario.")
            return

        assinatura_anterior = estado_anterior.get("signature", "")
        assinatura_nova = novo_estado["signature"]

        if assinatura_nova != assinatura_anterior and matches:
            registrar_log("Nova publicacao relevante detectada no ultimo diario.")
            aviso = formatar_alerta(matches)
            enviar_telegram(aviso)
            if os.name == "nt":
                ctypes.windll.user32.MessageBoxW(0, aviso, "Vila Velha - Nova publicacao", 0x40 | 0x1000)
        else:
            registrar_log("Nenhuma novidade relevante encontrada no ultimo diario.")

        salvar_estado(novo_estado)

    except Exception as erro:
        registrar_log(f"Resultado: [Erro Critico] - {erro}")


if __name__ == "__main__":
    monitorar()
