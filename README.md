# Fala

Ditado por voz em qualquer app — um clone brasileiro do [Wispr Flow](https://wisprflow.ai) para Linux.

Aperte o atalho, fale, aperte de novo: o Fala transcreve com Whisper, ajusta o texto com o Claude
(pontuação, tira os "é...", "tipo", entende "às 3, não, às 4") e cola no campo em foco.

## Como funciona

```
atalho do GNOME ──► fala toggle ──► socket ──► app (PyQt6)
                                                │
                     microfone (sounddevice) ◄──┤ gravando: pílula com medidor de volume
                                                │
                  Whisper (local ou Groq)  ◄────┤ transcrevendo…
                  Claude (ajuste do texto) ◄────┤ ajustando texto…
                                                │
                     wl-copy + ydotool Ctrl+V ◄─┘ texto aparece no app em foco
```

No Wayland, apps não podem capturar teclas globais nem digitar em outras janelas sozinhos. Por isso:
- o **atalho** é um atalho personalizado do GNOME que chama `fala toggle` (aperta uma vez para começar, outra para parar);
- a **colagem** usa `ydotool` (teclado virtual via uinput). Sem ele, o texto fica na área de transferência e você cola com Ctrl+V.

## Instalação (Fedora)

```bash
sudo dnf install portaudio wl-clipboard libnotify ydotool
sudo systemctl enable --now ydotool

git clone git@github.com:joaovmourasouza/fala.git && cd fala
python3 -m venv .venv
.venv/bin/pip install -e '.[local]'     # sem [local] se for usar só a Groq
```

Para o ajuste com IA, exporte sua chave da Anthropic (sem ela o Fala usa a transcrição bruta):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Se `ydotool` não conseguir acessar o socket do daemon, aponte para ele com `export YDOTOOL_SOCKET=/tmp/.ydotool_socket`
(o caminho depende de como o serviço foi configurado).

## Uso

```bash
.venv/bin/fala                         # inicia o app (deixe rodando)
scripts/setup-gnome-shortcut.sh        # cria o atalho Ctrl+Alt+Espaço → fala toggle
```

Outros comandos: `fala start`, `fala stop`, `fala cancel`, `fala quit`.

O primeiro uso do modo local baixa o modelo Whisper (~500 MB para `small`). Na CPU, uma frase leva ~2 s.

## Configuração

Copie `config.example.toml` para `~/.config/fala/config.toml`. Principais opções:

| Opção | Padrão | |
|---|---|---|
| `transcriber` | `local` | `local` (faster-whisper) ou `groq` (API, precisa de `GROQ_API_KEY`) |
| `whisper_model` | `small` / `whisper-large-v3-turbo` | modelo do Whisper |
| `cleanup` | `true` | ajuste do texto com Claude |
| `claude_model` | `claude-opus-5-5` | modelo do Claude |
| `claude_effort` | `low` | `low` deixa o ajuste mais rápido |
| `paste_keys` | `ctrl+v` | use `ctrl+shift+v` se dita muito em terminais |

## Roadmap

- [x] Gravação, transcrição local/Groq, ajuste com Claude, colagem, overlay, ícone na bandeja
- [ ] Modo segurar-para-falar (via evdev)
- [ ] Dicionário pessoal (nomes, jargões)
- [ ] Contexto do app em foco (tom de e-mail vs. chat)
- [ ] Restaurar a área de transferência depois de colar
- [ ] Iniciar com a sessão (autostart)

## Licença

MIT
