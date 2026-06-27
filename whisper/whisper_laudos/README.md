# whisper_laudos

Projeto local para transcricao fiel de audios medicos de tomografia computadorizada e ressonancia magnetica, com foco em portugues brasileiro e vocabulario radiologico.

As transcricoes geradas por este projeto sao rascunhos operacionais. Elas devem ser revisadas por profissional autorizado antes de qualquer uso clinico.

## Etapa 1 - Arquitetura recomendada

### Fluxo geral

1. Dados brutos entram em `dados_treinamento/originais/`.
2. `scripts/preparar_audio.py` convertera os audios para mono, 16 kHz, usando FFmpeg via `subprocess` sem `shell=True`.
3. `scripts/segmentar_dataset.py` dividira os audios longos em segmentos de 10 a 30 segundos, preferindo pausas de fala.
4. Transcricoes humanas revisadas ficarao em `dados_treinamento/transcricoes/`.
5. `scripts/criar_manifestos.py` gerara `train.jsonl`, `validation.jsonl` e `test.jsonl`, evitando vazamento do mesmo exame entre treino e teste.
6. `scripts/validar_dataset.py` verificara integridade, duracao, texto, duplicatas e inconsistencias antes do treinamento.
7. `scripts/treinar.py` refinara `openai/whisper-small` com LoRA/PEFT.
8. `scripts/avaliar.py` comparara o modelo base e o modelo refinado no mesmo conjunto de teste.
9. `scripts/transcrever.py` monitorara `audios/`, convertera novos arquivos e salvara laudos em `laudos/`.

Todo processamento deve permanecer local. Audios e transcricoes medicas nao devem ser enviados para servicos externos.

## Modelo base sugerido

A recomendacao inicial e usar `openai/whisper-small`.

Para uma RTX 3060 com 12 GB de VRAM, o `whisper-small` e o ponto de partida mais equilibrado: tem capacidade melhor que `tiny` e `base`, consome bem menos memoria que `medium`, e permite iteracoes mais rapidas com LoRA, validacao e ajustes de dataset.

O `whisper-medium` pode ser considerado depois, se houver dados suficientes e se a avaliacao mostrar que o `small` ainda erra termos criticos. O custo e maior consumo de VRAM, treinamento mais lento e maior risco de overfitting se o dataset for pequeno.

Importante: processador, tokenizador e modelo devem usar sempre a mesma base. Se o treinamento partir de `openai/whisper-small`, avaliacao e transcricao tambem devem carregar artefatos compativeis com `openai/whisper-small`.

## Estrategia LoRA

A estrategia recomendada e LoRA/PEFT, nao fine-tuning completo.

Motivos:

- reduz uso de VRAM;
- acelera experimentos;
- diminui risco de degradar conhecimentos gerais do Whisper;
- facilita manter o modelo base separado dos adaptadores;
- e mais adequado para comecar com dataset medico limitado.

Configuracao inicial proposta no `config.yaml`:

- rank LoRA: `32`;
- alpha: `64`;
- dropout: `0.05`;
- modulos alvo: `q_proj`, `v_proj`, `k_proj`, `out_proj`;
- batch efetivo: `batch_size * gradient_accumulation`.

Se o dataset inicial tiver poucos segmentos, rank `16` pode ser mais prudente. Se houver muitas horas revisadas e o ganho em termos criticos for insuficiente, rank `32` ou `64` pode ser testado.

## Limitacoes de memoria

Com `openai/whisper-small`, LoRA, FP16 e audio limitado a aproximadamente 30 segundos por amostra, a RTX 3060 de 12 GB deve ser suficiente para treinamento local. Ainda assim, a memoria depende de:

- duracao maxima dos segmentos;
- batch size;
- gradient accumulation;
- uso de gradient checkpointing;
- numero de beams na geracao;
- tamanho do modelo;
- outros processos usando a GPU.

Se ocorrer falta de VRAM, as primeiras medidas sao reduzir `batch_size`, ativar `gradient_checkpointing`, reduzir a duracao maxima dos segmentos ou usar LoRA rank menor.

## Riscos tecnicos

- Overfitting em poucos medicos, poucos aparelhos ou poucos tipos de exame.
- Vazamento de dados se segmentos do mesmo exame aparecerem em treino e teste.
- Transcricoes de referencia imperfeitas, especialmente se geradas automaticamente sem revisao humana.
- Degradacao de negacoes, lateralidade, numeros e medidas.
- Alucinacao ou repeticao em audios longos se forem enviados ao modelo como uma unica janela.
- Risco clinico caso a transcricao seja usada sem revisao.
- Risco de privacidade se audios, nomes, prontuarios ou exames forem mantidos sem controle de acesso.

## Criterios de avaliacao

O refinamento so sera considerado melhor se demonstrar ganho em dados nunca vistos. A avaliacao deve comparar o modelo base e o modelo refinado no mesmo `test.jsonl`.

Metricas obrigatorias:

- WER;
- CER;
- insercoes, omissoes e substituicoes;
- taxa de repeticao;
- acuracia em termos radiologicos criticos;
- erros de numeros e medidas;
- erros de lateralidade;
- erros em negacoes;
- erros em "com contraste" e "sem contraste".

A perda de treino isolada nao e criterio suficiente.

## Quantidade aproximada de dados

Para um primeiro experimento util, espere pelo menos 5 a 10 horas de audio revisado e segmentado. Para ganhos mais confiaveis em radiologia, 20 a 50 horas tendem a ser um alvo melhor. O ideal e ter diversidade de medicos, microfones, salas, exames, ritmos de ditado e termos anatomicos.

Mais importante que volume bruto: transcricao fiel, revisada e alinhada corretamente ao audio.

## Primeira etapa pratica

### 1. Criar o ambiente virtual

Execute no PowerShell, dentro desta pasta:

```powershell
cd C:\Users\jpedr\Desktop\python_projects\whisper\whisper_laudos
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Se a politica do PowerShell bloquear a ativacao, use:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. Conferir a estrutura inicial

```powershell
Get-ChildItem -Force
Get-ChildItem -Recurse dados_treinamento,modelos
```

Pastas esperadas:

- `audios/`
- `laudos/`
- `processados/`
- `erros/`
- `temp/`
- `dados_treinamento/originais/`
- `dados_treinamento/convertidos/`
- `dados_treinamento/segmentos/`
- `dados_treinamento/transcricoes/`
- `dados_treinamento/manifestos/`
- `modelos/checkpoints/`
- `modelos/final/`
- `scripts/`
- `logs/`

### 3. Conferir FFmpeg

Atualize `config.yaml` se o FFmpeg estiver em outro caminho:

```yaml
caminhos:
  ffmpeg_exe: "C:\\ffmpeg\\bin\\ffmpeg.exe"
```

Teste:

```powershell
& "C:\ffmpeg\bin\ffmpeg.exe" -version
```

## Proxima etapa

A proxima etapa e criar `scripts/criar_manifestos.py` e `scripts/validar_dataset.py`, depois que os segmentos tiverem transcricoes humanas revisadas.

## Etapa 2 - Preparacao e conversao dos audios

Arquivo criado:

```text
scripts/preparar_audio.py
```

Objetivo:

- ler audios em `dados_treinamento/originais/`;
- aceitar `.mp4`, `.m4a`, `.mp3`, `.wav` e `.flac`;
- validar arquivo vazio ou corrompido;
- converter com FFmpeg para mono, 16 kHz;
- salvar em `dados_treinamento/convertidos/`;
- preservar nomes com espacos e acentos;
- registrar logs em `logs/preparar_audio.log`;
- usar `subprocess` com lista de argumentos, sem `shell=True`.

Uso padrao:

```powershell
cd C:\Users\jpedr\Desktop\python_projects\whisper\whisper_laudos
.\venv\Scripts\python.exe scripts\preparar_audio.py
```

Usando caminho de FFmpeg pela linha de comando:

```powershell
.\venv\Scripts\python.exe scripts\preparar_audio.py --ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"
```

Usando variavel de ambiente:

```powershell
$env:FFMPEG_EXE = "C:\ffmpeg\bin\ffmpeg.exe"
.\venv\Scripts\python.exe scripts\preparar_audio.py
```

Converter para FLAC:

```powershell
.\venv\Scripts\python.exe scripts\preparar_audio.py --format flac
```

Reprocessar arquivos ja convertidos:

```powershell
.\venv\Scripts\python.exe scripts\preparar_audio.py --overwrite
```

Teste rapido:

1. Coloque um arquivo de audio ou video em:

```text
dados_treinamento/originais/
```

2. Rode:

```powershell
.\venv\Scripts\python.exe scripts\preparar_audio.py
```

3. Confira se foi gerado um arquivo `.wav` em:

```text
dados_treinamento/convertidos/
```

4. Confira o log:

```powershell
Get-Content logs\preparar_audio.log -Tail 50
```

## Etapa 3 - Segmentacao do dataset

Arquivo criado:

```text
scripts/segmentar_dataset.py
```

Objetivo:

- ler WAV/FLAC de `dados_treinamento/convertidos/`;
- detectar pausas com FFmpeg `silencedetect`;
- dividir audios longos em segmentos menores;
- preferir cortes em pausas da fala;
- manter segmentos em torno de 20 segundos;
- limitar segmentos a aproximadamente 30 segundos;
- salvar segmentos em `dados_treinamento/segmentos/`;
- gerar `dados_treinamento/manifestos/segmentos_sem_transcricao.jsonl`;
- gerar `dados_treinamento/manifestos/segmentos_sem_transcricao.csv`.

Este script nao cria transcricoes automaticamente. O manifesto gerado aponta o caminho esperado de cada `.txt`, mas o texto deve ser preenchido ou revisado por humano antes de treinamento.

Teste com poucos arquivos:

```powershell
.\venv\Scripts\python.exe scripts\segmentar_dataset.py --limit 3 --overwrite
```

Rodar em todo o dataset:

```powershell
.\venv\Scripts\python.exe scripts\segmentar_dataset.py --overwrite
```

Conferir quantidade de segmentos:

```powershell
(Get-ChildItem dados_treinamento\segmentos -Filter *.wav).Count
```

Conferir manifesto:

```powershell
Get-Content dados_treinamento\manifestos\segmentos_sem_transcricao.jsonl -TotalCount 5
```

Conferir log:

```powershell
Get-Content logs\segmentar_dataset.log -Tail 50
```

Alinhamento audio-texto:

- cada segmento gerado tem um `segment_id`;
- o audio fica em `dados_treinamento/segmentos/{segment_id}.wav`;
- a transcricao esperada fica em `dados_treinamento/transcricoes/{segment_id}.txt`;
- o texto deve corresponder exatamente ao trecho de audio segmentado;
- se um corte ficar ruim, o segmento deve ser ajustado ou removido antes do treinamento.

## Ciclo mensal de tuning supervisionado

Objetivo:

- receber audios novos da digitadora;
- gerar transcricao inicial com Whisper;
- receber PDF corrigido;
- extrair texto do PDF;
- comparar rascunho Whisper com texto corrigido;
- registrar o par para validacao;
- usar somente pares validados no proximo treino LoRA.

Estrutura:

```text
ciclo_tuning/
├── audios_recebidos/
├── transcricoes_whisper/
├── pdfs_corrigidos/
├── textos_corrigidos/
├── pares_validados/
├── rejeitados/
└── relatorios/
```

Regra clinica:

O PDF corrigido so deve entrar em treino se representar o que foi ditado no audio. Se o laudo final tiver sido reescrito, resumido ou tiver conteudo adicionado que nao foi falado, ele deve ser usado apenas como apoio de revisao, nao como verdade de treinamento.

Regra de nomes:

- o audio pode ter qualquer nome, mas deve ser `.mp4`;
- o laudo corrigido pode ter qualquer nome, mas deve ser `.pdf`;
- os dois devem ter exatamente o mesmo nome antes da extensao.

Exemplo valido:

```text
ciclo_tuning/audios_recebidos/RM joelho Maria 27-06.mp4
ciclo_tuning/pdfs_corrigidos/RM joelho Maria 27-06.pdf
```

Exemplo invalido:

```text
ciclo_tuning/audios_recebidos/RM joelho Maria 27-06.mp4
ciclo_tuning/pdfs_corrigidos/RM joelho Maria corrigido.pdf
```

Arquivo criado:

```text
scripts/registrar_correcao_pdf.py
```

Dependencia para extrair texto de PDF:

```powershell
.\venv\Scripts\python.exe -m pip install pymupdf
```

Uso:

```powershell
.\venv\Scripts\python.exe scripts\registrar_correcao_pdf.py "ciclo_tuning\pdfs_corrigidos\RM joelho Maria 27-06.pdf"
```

Com identificador explicito, caso o PDF venha de outra pasta:

```powershell
.\venv\Scripts\python.exe scripts\registrar_correcao_pdf.py "C:\caminho\RM joelho Maria 27-06.pdf" --case-id "RM joelho Maria 27-06"
```

O script gera:

```text
ciclo_tuning/textos_corrigidos/RM joelho Maria 27-06.txt
ciclo_tuning/relatorios/pares_ciclo.jsonl
ciclo_tuning/relatorios/pares_ciclo.csv
logs/registrar_correcao_pdf.log
```

Status possiveis:

- `pronto_para_validacao_humana`: existe audio, rascunho Whisper e similaridade aceitavel;
- `revisar_alinhamento`: existe comparacao, mas o texto corrigido diverge muito do rascunho;
- `pendente_audio`: PDF sem audio correspondente;
- `pendente_transcricao_whisper`: PDF com audio, mas sem rascunho Whisper;
- `pendente_comparacao`: nao foi possivel comparar textos.

O sistema nao treina automaticamente ao receber PDF. Ele acumula pares, gera relatorio e deixa a decisao de entrada no dataset para uma validacao posterior.
