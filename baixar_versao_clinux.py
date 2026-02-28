import os
import requests
from zipfile import ZipFile
#esse arquivo .txt precisa existir na pasta onde está o codigo, ele serve para guardar o último diretório informado pelo usuário.
ARQUIVO_DIRETORIO = "ultimo_diretorio.txt"

# -------------------------------
# Função para obter o diretório
# -------------------------------
def obter_diretorio():
    # Garante que o arquivo exista
    if not os.path.exists(ARQUIVO_DIRETORIO):
        with open(ARQUIVO_DIRETORIO, "w", encoding="utf-8") as f:
            f.write("")

    # Lê o último diretório salvo
    with open(ARQUIVO_DIRETORIO, "r", encoding="utf-8") as f:
        ultimo_diretorio = f.read().strip()

    # Se existir um diretório salvo, pergunta se quer usar
    if ultimo_diretorio and os.path.isdir(ultimo_diretorio):
        usar = input(f"Deseja usar o último diretório ({ultimo_diretorio})? [s/n]: ").lower()
        if usar == "s":
            return ultimo_diretorio

    # Loop até o usuário informar um diretório válido
    while True:
        novo_diretorio = input("Informe o diretório completo do Clinux: ").strip()
    
        if os.path.isdir(novo_diretorio):
            with open(ARQUIVO_DIRETORIO, "w", encoding="utf-8") as f:
                f.write(novo_diretorio)
            return novo_diretorio
        else:
            print("Diretório não existe. Informe um caminho válido.")



# Função para baixar a versão do Clinux
def baixar_versao():
    # Solicita a versão do Clinux ao usuário
    versao_clinux = input("Versão do Clinux (por exemplo, 30866): ")
    #obtem o diretorio da função obter_diretorio(), feita acima.
    diretorio_clinux = obter_diretorio()
    #encontra a versão do clinux no FTP de acordo com o que for informado no input.
    nome_do_clinux = f"clinux_{versao_clinux}.zip"
    #acessa o diretório do clinux.
    file_path = os.path.join(diretorio_clinux, nome_do_clinux)

    #endereço e senha do FTP, precisa ver uma forma de esconder isso depois, para não deixar exposto no código.
    ftp = f"https://ftp/versoes/{nome_do_clinux}"
    usuario = 
    senha = 
    #faz a requisição para baixar o arquivo do FTP usando as credenciais fornecidas.
    resposta = requests.get(ftp, auth=(usuario, senha))
    
    #condição do request se for diferente de 200 (OK), exibe uma mensagem de erro e retorna None para ambos diretório e versão.
    if resposta.status_code != 200:
        print(f"Versão {versao_clinux} indisponível no FTP ou não existe.")
        return None, None
    
    #solução do chatgpt, não tenho ideia do que isso ta fazendo, mas acho que serve para salvar o arquivo baixado do FTP no diretório.
    with open(file_path, "wb") as file:
        file.write(resposta.content)

    print(f"Arquivo {nome_do_clinux} baixado com sucesso!")

    return diretorio_clinux, versao_clinux

#quando for baixado o arquivo .zip do FTP, ele vai extrair o clinux.exe e renomear para clinux_versao.exe.
def extrair_arquivo_e_renomear(diretorio_clinux, versao_clinux):
    # Define o caminho do arquivo ZIP baixado
    zip_path = os.path.join(diretorio_clinux, f"clinux_{versao_clinux}.zip")

    print("Tentando extrair:", zip_path)
    # Verifica se o arquivo ZIP existe antes de tentar extrair
    if not os.path.exists(zip_path):
        print("ERRO: Arquivo ZIP não encontrado.")
        return
    # esse aqui tambem foi pelo gepetas, preciso estudar isso.
    with ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(diretorio_clinux)

    print("ZIP extraído com sucesso.")

    # Procura clinux.exe após extração
    exe_encontrado = None
    for raiz, _, arquivos in os.walk(diretorio_clinux):
        for arquivo in arquivos:
            if arquivo.lower() == "clinux.exe":
                exe_encontrado = os.path.join(raiz, arquivo)
                break
    # Se o clinux.exe não for encontrado, exibe um erro e retorna
    if not exe_encontrado:
        print("ERRO: clinux.exe não encontrado após extração.")
        return
    # resultado final do clinux e do caminho.
    nome_final = f"clinux_{versao_clinux}.exe"
    caminho_final = os.path.join(diretorio_clinux, nome_final)

    # função para arquivo que já existe, pergunta se quer sobrescrever, cancelar ou renomear.
    if os.path.exists(caminho_final):
        print(f"O arquivo {nome_final} já existe.")

        while True:
            opcao = input("Deseja sobrescrever? [s] sim | [n] não | [r] renomear: ").lower()

            if opcao == "s":
                os.remove(caminho_final)
                break

            elif opcao == "n":
                print("Operação cancelada pelo usuário.")
                return

            elif opcao == "r":
                contador = 1
                while True:
                    novo_nome = f"clinux_{versao_clinux}_{contador}.exe"
                    novo_caminho = os.path.join(diretorio_clinux, novo_nome)
                    if not os.path.exists(novo_caminho):
                        caminho_final = novo_caminho
                        break
                    contador += 1
                break

            else:
                print("Opção inválida. Use s, n ou r.")

    # Renomeia/move o executável
    os.rename(exe_encontrado, caminho_final)

    print("Arquivo final criado com sucesso:")
    print(caminho_final)

    # Remove o ZIP após sucesso
    os.remove(zip_path)
    print("Arquivo ZIP removido com sucesso.")


#não tenho ideia do que essa porra faz, preciso parar de usar o chatgpt pra tudo, mas basicamente ele chama a função de baixar a versão do clinux, e se for bem sucedida, chama a função para extrair e renomear o arquivo.
diretorio, versao = baixar_versao()

if diretorio and versao:
    extrair_arquivo_e_renomear(diretorio, versao)