---
name: cordel
description: Faz vídeo explicativo curto (9:16, 16:9 ou 1:1) SEMPRE no estilo visual "cordel" descrito em references/estilo.md. Recebe tema, formato, duração, resolução e motor; planeja as cenas, desenha os storyboards no estilo, escreve a narração, anima, põe uma trilha única e entrega final/video-final.mp4 + final/manifesto.json conferidos. Use quando pedirem "vídeo no estilo cordel", "usa a skill cordel" ou um vídeo explicativo com esta cara.
---

# Skill de estilo: cordel

Esta skill faz vídeos sempre com a mesma cara. O ESTILO está em `references/estilo.md` (a bíblia).
O CONTEÚDO vem do pedido. Nunca copie personagens, logos ou textos do vídeo que inspirou o estilo.

`SKILL_DIR` = a pasta deste arquivo. Os scripts ficam em `SKILL_DIR/scripts/` e rodam com `python3`.
Trabalhe numa pasta de projeto do vídeo (padrão: a pasta atual). Tudo vai para `saida/` e `final/` dela.

## Antes de tudo
1. Leia `references/estilo.md`, `references/regras-storyboard.md`, `references/regras-video.md` e,
   se existir, `references/licoes.md` (o que já deu errado com este estilo).
2. Confira as ferramentas: `ffmpeg -version`, `python3 -c "import PIL"`. Faltou algo → diga o que instalar e pare.

## Passo 1 — os 5 dados (pergunte em texto livre o que faltar, sugerindo o padrão)
| dado | opções | padrão |
|---|---|---|
| tema | uma frase | — (obrigatório) |
| formato | 9:16 · 16:9 · 1:1 | 9:16 |
| duração | segundos; vira múltiplo de 2,5 | 15 |
| resolução | ex.: 1080x1920 | a do formato (9:16 → 1080x1920, 16:9 → 1920x1080, 1:1 → 1080x1080) |
| motor | `local` (grátis, testado) · `kling` · `seedance` (só prompts, **não testados**) | local |

## Passo 2 — plano das cenas
```bash
python3 SKILL_DIR/scripts/cenas.py --tema "<tema>" --duracao <s> --formato <f> --resolucao <WxH> --motor <m>
```
Mostra quantas cenas (2,5 s cada) e storyboards (até 6 cenas cada). Se avisar que normalizou a duração, conte ao usuário.

## Passo 3 — roteiro (você escreve)
Escreva `roteiro.json` com uma entrada por cena (`texto_tela`, `fala`, `acao`, `camera`) seguindo
`references/regras-video.md` (fala de até 6 palavras por cena, uma palavra-chave grande por cena, a 1ª cena
abre pela dor ou pelo desejo de quem vê, em "você"). Depois:
```bash
python3 SKILL_DIR/scripts/cenas.py ... --roteiro roteiro.json     # mesmo comando + o roteiro
```

## Passo 4 — storyboards no estilo
Para cada storyboard do `saida/plano.json`, monte o pedido com `modelos/prompt-storyboard.md` (preencha com a
bíblia + as cenas daquele storyboard) e gere UMA imagem com a sua ferramenta de imagem (Codex: `image_gen`;
Claude Code: a ferramenta de imagem que você tiver, ou peça ao usuário para gerar e salvar).
Salve em `saida/storyboards/storyboard-N.png`.
- Gere um de cada vez. Do 2º em diante, passe o storyboard anterior como imagem de referência (continuidade).
- **Abra a imagem e confira** com a lista de `regras-storyboard.md` (grade certa, palavra exata letra por letra,
  estilo, continuidade). Amplie as palavras para conferir. Ruim → refaça (até 2 vezes) e anote em `references/licoes.md`.

## Passo 5 — recortar
```bash
python3 SKILL_DIR/scripts/recortar.py --plano saida/plano.json
```

## Passo 6 — animar
```bash
python3 SKILL_DIR/scripts/animar.py                      # motor local: zoom/pan lento + dissolve
python3 SKILL_DIR/scripts/animar.py --motor kling --so-prompts      # NÃO TESTADO: só escreve os comandos
python3 SKILL_DIR/scripts/animar.py --motor seedance --so-prompts   # NÃO TESTADO: só escreve os prompts
```
Com kling/seedance, quem roda é o usuário, na conta dele; depois os clipes voltam para `saida/clipes/`.

## Passo 7 — narração (uma voz só)
```bash
python3 SKILL_DIR/scripts/narrar.py --arquivo voz.wav            # o usuário gravou tudo
python3 SKILL_DIR/scripts/narrar.py --falas-dir falas/           # o usuário gravou uma fala por cena
python3 SKILL_DIR/scripts/narrar.py --comando '<tts> {texto} {saida}'   # qualquer TTS local
python3 SKILL_DIR/scripts/narrar.py --inemavox --inemavox-dir <pasta> --ref <voz.wav>
python3 SKILL_DIR/scripts/narrar.py --edge                       # NÃO TESTADO (serviço online)
```
Se avisar que uma fala passou da cena, encurte a fala no roteiro e rode de novo.

## Passo 8 — montar com trilha única
```bash
python3 SKILL_DIR/scripts/montar.py [--trilha assets/trilha/x.mp3] [--volume 0.5]
```
Sem trilha em `assets/trilha/` → pergunte ao usuário qual música usar (dele ou com licença). Várias → peça para escolher.

## Passo 9 — conferir (obrigatório)
```bash
python3 SKILL_DIR/scripts/validar.py --duracao <s> --resolucao <WxH>
python3 SKILL_DIR/scripts/folha.py                 # final/folha-final.jpg: um quadro de cada cena
```
Só diga **"pronto"** depois que o `validar.py` imprimir `PASSOU` e você OLHAR a `final/folha-final.jpg`
(texto legível, sem letra trocada, estilo igual em todos os painéis). Se falhar, diga o que falta.

## Passo 10 — melhore a skill
Depois de cada vídeo, escreva em `references/licoes.md` (uma linha por item) o que saiu errado e a regra que
evitaria. Se for regra de estilo ou de storyboard, mude também `estilo.md`/`regras-storyboard.md`, não só o prompt.
