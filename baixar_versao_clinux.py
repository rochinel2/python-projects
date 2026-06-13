import os
from getpass import getpass
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

import requests


# Esse arquivo .txt precisa existir na pasta onde esta o codigo.
# Ele guarda o ultimo diretorio informado pelo usuario.
ARQUIVO_DIRETORIO = "ultimo_diretorio.txt"
ARQUIVO_CONFIG = "config_clinux.xml"
FTP_BASE_URL = "https://gdicomvixnew.zapto.org/versoes/"


def obter_diretorio():
    """Obtem e salva o diretorio onde o Clinux sera baixado."""
    if not os.path.exists(ARQUIVO_DIRETORIO):
        with open(ARQUIVO_DIRETORIO, "w", encoding="utf-8") as f:
            f.write("")

    with open(ARQUIVO_DIRETORIO, "r", encoding="utf-8") as f:
        ultimo_diretorio = f.read().strip()

    if ultimo_diretorio and os.path.isdir(ultimo_diretorio):
        usar = input(f"Deseja usar o ultimo diretorio ({ultimo_diretorio})? [s/n]: ").strip().lower()
        if usar == "s":
            return ultimo_diretorio

    while True:
        novo_diretorio = input("Informe o diretorio completo do Clinux: ").strip().strip('"')

        if os.path.isdir(novo_diretorio):
            with open(ARQUIVO_DIRETORIO, "w", encoding="utf-8") as f:
                f.write(novo_diretorio)
            return novo_diretorio

        print("Diretorio nao existe. Informe um caminho valido.")


def ler_credenciais_xml():
    if not os.path.exists(ARQUIVO_CONFIG):
        return None, None

    try:
        raiz = ET.parse(ARQUIVO_CONFIG).getroot()
    except ET.ParseError:
        print(f"Arquivo {ARQUIVO_CONFIG} invalido. Vou pedir os dados novamente.")
        return None, None

    usuario = raiz.findtext("ftp/usuario", default="").strip()
    senha = raiz.findtext("ftp/senha", default="")
    return usuario or None, senha or None


def salvar_credenciais_xml(usuario, senha):
    raiz = ET.Element("config")
    ftp = ET.SubElement(raiz, "ftp")
    ET.SubElement(ftp, "usuario").text = usuario
    ET.SubElement(ftp, "senha").text = senha

    arvore = ET.ElementTree(raiz)
    ET.indent(arvore, space="    ")
    arvore.write(ARQUIVO_CONFIG, encoding="utf-8", xml_declaration=True)


def pedir_e_salvar_credenciais():
    print(f"Credenciais do FTP nao encontradas em {ARQUIVO_CONFIG}.")
    usuario = input("Usuario do FTP: ").strip()
    senha = getpass("Senha do FTP: ")

    salvar_credenciais_xml(usuario, senha)
    print(f"Credenciais salvas em {ARQUIVO_CONFIG}.")
    return usuario, senha


def obter_credenciais():
    """Le credenciais do ambiente, do XML ou pergunta ao usuario."""
    usuario = os.getenv("CLINUX_FTP_USUARIO")
    senha = os.getenv("CLINUX_FTP_SENHA")

    if usuario and senha:
        return usuario, senha

    usuario_xml, senha_xml = ler_credenciais_xml()
    if usuario_xml and senha_xml:
        return usuario_xml, senha_xml

    return pedir_e_salvar_credenciais()


def baixar_versao():
    versao_clinux = input("Versao do Clinux (por exemplo, 30866): ").strip()

    if not versao_clinux:
        print("Versao nao informada.")
        return None, None

    diretorio_clinux = obter_diretorio()
    nome_do_clinux = f"clinux_{versao_clinux}.zip"
    file_path = os.path.join(diretorio_clinux, nome_do_clinux)
    ftp_url = f"{FTP_BASE_URL.rstrip('/')}/{nome_do_clinux}"
    usuario, senha = obter_credenciais()

    try:
        resposta = requests.get(ftp_url, auth=(usuario, senha), timeout=60)
        resposta.raise_for_status()
    except requests.exceptions.HTTPError:
        status = resposta.status_code
        if status == 401:
            print("Usuario ou senha do FTP invalidos.")
        elif status == 404:
            print(f"Versao {versao_clinux} indisponivel no FTP ou nao existe.")
        else:
            print(f"Erro HTTP ao baixar o arquivo: {status}")
        return None, None
    except requests.exceptions.RequestException as erro:
        print(f"Erro de conexao ao baixar o arquivo: {erro}")
        return None, None

    with open(file_path, "wb") as file:
        file.write(resposta.content)

    print(f"Arquivo {nome_do_clinux} baixado com sucesso!")
    return diretorio_clinux, versao_clinux


def extrair_arquivo_e_renomear(diretorio_clinux, versao_clinux):
    zip_path = os.path.join(diretorio_clinux, f"clinux_{versao_clinux}.zip")

    print("Tentando extrair:", zip_path)
    if not os.path.exists(zip_path):
        print("ERRO: Arquivo ZIP nao encontrado.")
        return False

    try:
        with ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(diretorio_clinux)
    except BadZipFile:
        print("ERRO: O arquivo baixado nao e um ZIP valido.")
        return False

    print("ZIP extraido com sucesso.")

    exe_encontrado = None
    for raiz, _, arquivos in os.walk(diretorio_clinux):
        for arquivo in arquivos:
            if arquivo.lower() == "clinux.exe":
                exe_encontrado = os.path.join(raiz, arquivo)
                break
        if exe_encontrado:
            break

    if not exe_encontrado:
        print("ERRO: clinux.exe nao encontrado apos extracao.")
        return False

    nome_final = f"clinux_{versao_clinux}.exe"
    caminho_final = os.path.join(diretorio_clinux, nome_final)

    if os.path.exists(caminho_final):
        print(f"O arquivo {nome_final} ja existe.")

        while True:
            opcao = input("Deseja sobrescrever? [s] sim | [n] nao | [r] renomear: ").strip().lower()

            if opcao == "s":
                os.remove(caminho_final)
                break

            if opcao == "n":
                print("Operacao cancelada pelo usuario.")
                return False

            if opcao == "r":
                contador = 1
                while True:
                    nome_backup = f"clinux_{versao_clinux}_{contador}.exe"
                    caminho_backup = os.path.join(diretorio_clinux, nome_backup)
                    if not os.path.exists(caminho_backup):
                        os.rename(caminho_final, caminho_backup)
                        print(f"Arquivo existente renomeado para: {nome_backup}")
                        break
                    contador += 1
                break

            print("Opcao invalida. Use s, n ou r.")

    os.rename(exe_encontrado, caminho_final)

    print("Arquivo final criado com sucesso:")
    print(caminho_final)

    os.remove(zip_path)
    print("Arquivo ZIP removido com sucesso.")
    return True


def perguntar_sim_ou_nao(mensagem):
    while True:
        opcao = input(f"\n{mensagem} [s/n]: ").strip().lower()

        if opcao in ("s", "sim"):
            return True

        if opcao in ("n", "nao"):
            return False

        print("Opcao invalida. Use s ou n.")


def executar():
    while True:
        try:
            diretorio, versao = baixar_versao()

            if diretorio and versao and extrair_arquivo_e_renomear(diretorio, versao):
                if not perguntar_sim_ou_nao("Deseja baixar outra versao?"):
                    return
                continue
        except Exception as erro:
            print(f"\nERRO inesperado: {erro}")

        if not perguntar_sim_ou_nao("Deseja tentar novamente com outra versao?"):
            return


def pausar_antes_de_sair():
    input("\nPressione Enter para fechar...")


if __name__ == "__main__":
    try:
        executar()
    finally:
        pausar_antes_de_sair()
