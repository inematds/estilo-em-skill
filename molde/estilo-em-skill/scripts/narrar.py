#!/usr/bin/env python3
"""narrar.py — narração numa voz só para o vídeo todo, cada fala encaixada na sua cena.

Modos (escolha um):
  --arquivo voz.wav            você gravou a narração inteira (um arquivo só; vai do início ao fim)
  --falas-dir pasta/           você gravou uma fala por cena: cena-01.wav, cena-02.wav ... (mp3/m4a também)
  --inemavox --inemavox-dir D --ref voz-ref.wav [--engine chatterbox]
                               TTS local do inemavox (D/tts_direct.py), clonando a voz de referência
  --edge [--voz pt-BR-AntonioNeural]
                               edge-tts (NÃO TESTADO neste kit: usa um serviço online da Microsoft)
  --comando 'modelo'           qualquer TTS por linha de comando; {texto} e {saida} (pasta) são trocados.
                               O comando deve criar UM arquivo de áudio dentro de {saida}.

Encaixe: corta o silêncio das pontas de cada fala, põe no começo da sua cena (+0,12 s). Se a fala
passar do tempo da cena, acelera até 15% (atempo); se ainda não couber, avisa e sugere encurtar.
Confere que cada fala e a narração final NÃO são silêncio (já houve TTS que gravava áudio mudo sem erro).

Saída: saida/voz/narracao.wav (48 kHz mono, duração exata do vídeo) + saida/voz/encaixe.json
"""
from __future__ import annotations

import argparse
import array
import shlex
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import CENA_S, aviso, duracao, erro, gravar_json, ler_json, precisa, rodar, volume  # noqa: E402

TAXA = 48000
FOLGA_INICIO = 0.12
FOLGA_FIM = 0.10
ACELERA_MAX = 1.15
SILENCIO_DB = -40.0      # pico abaixo disso = áudio mudo
EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac")


def ler_pcm(arquivo: Path, filtro: str | None = None) -> array.array:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(arquivo)]
    if filtro:
        cmd += ["-af", filtro]
    cmd += ["-ac", "1", "-ar", str(TAXA), "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0:
        erro(f"não consegui ler o áudio {arquivo}: {r.stderr.decode(errors='ignore')[-300:]}")
    a = array.array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    return a


def gravar_wav(destino: Path, amostras: array.array):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(amostras.tobytes())


def pico_db(a: array.array) -> float:
    import math
    p = max((abs(x) for x in a), default=0)
    return -math.inf if p == 0 else 20 * math.log10(p / 32768)


CORTA_PONTAS = ("silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.05,"
                "areverse,silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.05,areverse")


def limite_fala(texto: str) -> float:
    """Duração máxima razoável de uma fala (s). Acima disso o TTS provavelmente inventou um pedaço a mais
    (visto com chatterbox em frases curtas: 4 palavras viraram 4,6 s)."""
    return 0.42 * len(texto.split()) + 0.9


def tts_uma(modo, texto: str, pasta_fala: Path, a) -> Path:
    if pasta_fala.exists():
        shutil.rmtree(pasta_fala)
    pasta_fala.mkdir(parents=True)
    if modo == "edge":
        precisa("edge-tts")
        destino = pasta_fala / "fala.mp3"
        r = subprocess.run(["edge-tts", "--voice", a.voz, "--text", texto, "--write-media", str(destino)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            erro(f"edge-tts falhou: {r.stderr[-300:]}")
        return destino
    if modo == "inemavox":
        script = Path(a.inemavox_dir).expanduser() / "tts_direct.py"
        if not script.exists():
            erro(f"não achei {script}; informe --inemavox-dir com a pasta do inemavox")
        cmd = ["python3", str(script), "--text", texto, "--lang", a.lingua, "--engine", a.engine,
               "--outdir", str(pasta_fala)]
        if a.ref:
            cmd += ["--ref", str(Path(a.ref).expanduser())]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            erro(f"TTS do inemavox falhou ({r.returncode}): {r.stderr[-500:]}")
    else:  # comando livre
        cmd = a.comando.replace("{texto}", shlex.quote(texto)).replace("{saida}", shlex.quote(str(pasta_fala)))
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            erro(f"comando de TTS falhou ({r.returncode}): {r.stderr[-500:]}")
    candidatos = [p for p in pasta_fala.rglob("*") if p.suffix.lower() in EXTS and "ref" not in p.stem
                  and "source" not in p.stem]
    if not candidatos:
        erro(f"o TTS não criou nenhum áudio em {pasta_fala}")
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def main():
    ap = argparse.ArgumentParser(description="Narração numa voz só, encaixada nas cenas")
    ap.add_argument("--pasta", default=".")
    ap.add_argument("--plano", default="saida/plano.json")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--arquivo", help="narração inteira gravada por você")
    g.add_argument("--falas-dir", help="uma fala gravada por cena (cena-01.wav ...)")
    g.add_argument("--inemavox", action="store_true")
    g.add_argument("--edge", action="store_true")
    g.add_argument("--comando")
    ap.add_argument("--inemavox-dir", default="")
    ap.add_argument("--ref", help="áudio de referência da voz (inemavox/chatterbox)")
    ap.add_argument("--engine", default="chatterbox")
    ap.add_argument("--lingua", default="pt")
    ap.add_argument("--voz", default="pt-BR-AntonioNeural", help="voz do edge-tts")
    ap.add_argument("--tentativas", type=int, default=3,
                    help="TTS: gera de novo a fala longa demais para o nº de palavras (fica a mais curta)")
    a = ap.parse_args()

    precisa("ffmpeg")
    pasta = Path(a.pasta)
    plano = ler_json(pasta / a.plano)
    total = plano["duracao_s"]
    n_total = round(total * TAXA)
    voz_dir = pasta / "saida" / "voz"
    voz_dir.mkdir(parents=True, exist_ok=True)
    destino = voz_dir / "narracao.wav"
    relatorio = {"modo": None, "duracao_s": total, "falas": [], "avisos": []}

    if a.arquivo:
        relatorio["modo"] = "arquivo"
        pcm = ler_pcm(Path(a.arquivo))
        if len(pcm) > n_total:
            aviso(f"a gravação tem {len(pcm) / TAXA:.1f} s e o vídeo {total:g} s; o fim será cortado")
            relatorio["avisos"].append("gravação maior que o vídeo: cortada")
        buf = array.array("h", pcm[:n_total])
        buf.extend([0] * (n_total - len(buf)))
    else:
        modo = "falas" if a.falas_dir else "inemavox" if a.inemavox else "edge" if a.edge else "comando"
        relatorio["modo"] = modo
        buf = array.array("h", [0] * n_total)
        cursor = 0.0
        for c in plano["cenas"]:
            texto = (c.get("fala") or "").strip()
            if not texto:
                continue
            if texto == "PREENCHER":
                erro(f"a fala da cena {c['numero']} ainda está como PREENCHER no plano")
            if modo == "falas":
                achados = [p for p in Path(a.falas_dir).glob(f"cena-{c['numero']:02d}.*") if p.suffix.lower() in EXTS]
                if not achados:
                    aviso(f"sem gravação para a cena {c['numero']} em {a.falas_dir}; cena fica sem fala")
                    continue
                bruto = achados[0]
            else:
                print(f"  voz da cena {c['numero']}: {texto}", flush=True)
                melhor = None
                for tent in range(1, max(1, a.tentativas) + 1):
                    arq = tts_uma(modo, texto, voz_dir / "falas" / f"cena-{c['numero']:02d}-t{tent}", a)
                    d = len(ler_pcm(arq, CORTA_PONTAS)) / TAXA
                    if melhor is None or d < melhor[1]:
                        melhor = (arq, d)
                    if d <= limite_fala(texto):
                        break
                    print(f"    {d:.2f} s é demais para {len(texto.split())} palavras (limite {limite_fala(texto):.2f} s); "
                          f"gerando de novo", flush=True)
                bruto = melhor[0]
            pcm = ler_pcm(bruto, CORTA_PONTAS)
            if not pcm or pico_db(pcm) < SILENCIO_DB:
                erro(f"a fala da cena {c['numero']} saiu MUDA (pico {pico_db(pcm) if pcm else '-inf'} dB) em {bruto}. "
                     "Confira o motor de voz antes de seguir.")
            dur = len(pcm) / TAXA
            vaga = CENA_S - FOLGA_INICIO - FOLGA_FIM
            acel = 1.0
            if dur > vaga:
                acel = min(ACELERA_MAX, dur / vaga)
                pcm = ler_pcm(bruto, f"{CORTA_PONTAS},atempo={acel:.4f}")
                dur = len(pcm) / TAXA
            inicio = max(c["inicio_s"] + FOLGA_INICIO, cursor + 0.08)
            fim = inicio + dur
            info = {"cena": c["numero"], "texto": texto, "inicio_s": round(inicio, 3), "fim_s": round(fim, 3),
                    "duracao_s": round(dur, 3), "acelerou": round(acel, 3), "arquivo": str(bruto)}
            if fim > c["fim_s"] + 0.05:
                palavras = len(texto.split())
                if dur <= vaga:
                    dica = "a fala anterior empurrou esta: encurte a fala da cena anterior"
                else:
                    dica = f"encurte para ~{max(2, int(palavras * vaga / dur))} palavras"
                msg = (f"a fala da cena {c['numero']} ({dur:.2f} s) passa {fim - c['fim_s']:.2f} s do fim da cena; {dica}")
                aviso(msg)
                info["aviso"] = msg
                relatorio["avisos"].append(msg)
            if fim > total:
                erro(f"a fala da cena {c['numero']} termina em {fim:.2f} s, depois do fim do vídeo ({total:g} s); encurte")
            ini_a = round(inicio * TAXA)
            for i, x in enumerate(pcm):
                v = buf[ini_a + i] + x
                buf[ini_a + i] = 32767 if v > 32767 else -32768 if v < -32768 else v
            cursor = fim
            relatorio["falas"].append(info)

    cru = voz_dir / "narracao-crua.wav"
    gravar_wav(cru, buf)
    if pico_db(buf) < SILENCIO_DB:
        erro("a narração inteira saiu muda; nada foi gravado como pronto")
    # nivela a voz (-16 LUFS) e garante a duração exata
    rodar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(cru), "-af",
           f"loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total}", "-ar", str(TAXA), "-ac", "1", str(destino)])
    vol = volume(destino)
    relatorio.update({"arquivo": "saida/voz/narracao.wav", "volume_medio_db": vol["mean"], "pico_db": vol["max"],
                      "duracao_real_s": round(duracao(destino), 3)})
    if vol["max"] < SILENCIO_DB:
        erro(f"narração final muda (pico {vol['max']} dB)")
    gravar_json(voz_dir / "encaixe.json", relatorio)
    print(f"narração: {destino} ({relatorio['duracao_real_s']} s, média {vol['mean']} dB, pico {vol['max']} dB, "
          f"{len(relatorio['falas'])} falas, {len(relatorio['avisos'])} avisos)")


if __name__ == "__main__":
    main()
