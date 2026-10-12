# Fala

Ditado por voz em qualquer app — um clone brasileiro do [Wispr Flow](https://wisprflow.ai) para Linux.

Aperte **Super+D** (de ditar) e fale: o Fala transcreve com Whisper, ajusta o texto com o Claude Code (`claude -p`)
(pontuação, tira os "é...", "tipo", entende "às 3, não, às 4") e digita no app em foco.

## Como funciona

- **Atalho global** (padrão **Super+D**) registrado pelo portal de atalhos do GNOME:
  toque rápido liga/desliga a gravação; segurando, grava enquanto a tecla estiver apertada.
- Enquanto grava, uma pílula na parte de baixo da tela mostra o volume da sua voz.
- **Transcrição** com Whisper (local, via faster-whisper, ou pela API da Groq).
- **Ajuste do texto** com `claude -p`, usando o login do Claude Code da sua máquina: pontuação,
  remove muletas, entende autocorreções e classifica o tipo de texto para as estatísticas.
- **Digita na janela em foco**: copia para a área de transferência e cola com Ctrl+V pelo portal
  de controle remoto do GNOME (na primeira vez ele pede permissão e depois lembra).
- **Roda em segundo plano** e inicia junto com a sessão; fechar a janela não encerra o app.
- **Painel Insights**: palavras por minuto, correções, total ditado, uso por tipo de texto,
  sequência de dias e histórico de ditados.

## Instalação (Flatpak)

Requisitos: `flatpak`, o remoto Flathub e o [Claude Code](https://claude.com/claude-code) instalado e logado.

```bash
flatpak install --user flathub org.flatpak.Builder org.freedesktop.Sdk//25.08
git clone git@github.com:joaovmourasouza/fala.git && cd fala
flatpak run org.flatpak.Builder --user --install --force-clean build-dir flatpak/io.github.joaovmourasouza.Fala.yml
```

Abra **Fala** pela lista de aplicativos. Na primeira vez o GNOME vai pedir para:
1. confirmar o atalho Super+D;
2. permitir que o Fala controle o teclado (para colar o texto);
3. permitir rodar em segundo plano.

O primeiro ditado baixa o modelo Whisper (~500 MB para `small`). Na CPU, uma frase leva ~2 s
para transcrever e ~4 s para o ajuste com o Claude.

Linha de comando: `flatpak run io.github.joaovmourasouza.Fala [show|toggle|start|stop|cancel|quit]`.

### Rodar sem Flatpak (desenvolvimento)

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[local]'
scripts/install-desktop-entry.sh   # o GNOME precisa do .desktop para liberar os portais
.venv/bin/fala
```

## Configuração

Pelo ícone de engrenagem no painel (no Flatpak o arquivo fica em
`~/.var/app/io.github.joaovmourasouza.Fala/config/fala/config.toml`). Principais opções:

| Opção | Padrão | |
|---|---|---|
| `transcriber` | `local` | `local` (faster-whisper) ou `groq` (API, precisa de `GROQ_API_KEY`) |
| `whisper_model` | `small` / `whisper-large-v3-turbo` | modelo do Whisper |
| `cleanup` | `true` | ajuste do texto com `claude -p` |
| `claude_model` | `claude-opus-5-5` | modelo passado em `--model` (aceita `opus`, `sonnet`, `haiku`) |
| `claude_effort` | `low` | passado em `--effort`; `low` deixa o ajuste mais rápido |
| `paste_keys` | `ctrl+v` | use `ctrl+shift+v` se dita muito em terminais |
| `shortcut` | `LOGO+d` | atalho sugerido ao GNOME (troque em Configurações > Teclado) |
| `autostart` | `true` | iniciar com a sessão |

## Roadmap

- [x] Gravação, transcrição local/Groq, ajuste com Claude, colagem, overlay
- [x] Atalho global com segurar-para-falar, segundo plano, Flatpak
- [x] Painel Insights e histórico
- [ ] Dicionário pessoal (nomes, jargões)
- [ ] Contexto do app em foco (tom de e-mail vs. chat)
- [ ] Restaurar a área de transferência depois de colar

## Licença

MIT
