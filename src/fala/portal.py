"""Portais do xdg-desktop-portal: o jeito suportado de, no Wayland e no Flatpak, um app
enviar teclas para outras janelas, registrar atalhos globais e rodar em segundo plano."""

import os
import secrets
import threading
from collections.abc import Callable
from pathlib import Path

from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
from jeepney.io.blocking import DBusConnection, Proxy, open_dbus_connection

APP_ID = "io.github.joaovmourasouza.Fala"
DESKTOP_PATH = "/org/freedesktop/portal/desktop"
IN_FLATPAK = os.path.exists("/.flatpak-info")
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "fala"


def _portal(interface: str) -> DBusAddress:
    return DBusAddress(DESKTOP_PATH, bus_name="org.freedesktop.portal.Desktop",
                       interface=f"org.freedesktop.portal.{interface}")


class PortalError(RuntimeError):
    pass


def connect() -> DBusConnection:
    """Conexão D-Bus identificada como o Fala perante os portais.

    No Flatpak o ID vem do sandbox; fora dele, cada conexão precisa se registrar
    (exige o .desktop instalado com esse ID, veja scripts/install-desktop-entry.sh).
    """
    conn = open_dbus_connection(bus="SESSION")
    if not IN_FLATPAK:
        registry = DBusAddress(DESKTOP_PATH, bus_name="org.freedesktop.portal.Desktop",
                               interface="org.freedesktop.host.portal.Registry")
        conn.send_and_get_reply(new_method_call(registry, "Register", "sa{sv}", (APP_ID, {})), timeout=5)
    return conn


def _token() -> str:
    return "fala_" + secrets.token_hex(8)


def request(conn: DBusConnection, interface: str, method: str, signature: str,
            make_body: Callable[[dict], tuple], extra: dict | None = None, timeout: float = 30) -> dict:
    """Chama um método de portal e espera o sinal Response do objeto Request correspondente."""
    token = _token()
    sender = conn.unique_name.lstrip(":").replace(".", "_")
    path = f"{DESKTOP_PATH}/request/{sender}/{token}"
    rule = MatchRule(type="signal", interface="org.freedesktop.portal.Request", member="Response", path=path)
    Proxy(message_bus, conn).AddMatch(rule)

    options = {"handle_token": ("s", token), **(extra or {})}
    with conn.filter(rule) as queue:
        reply = conn.send_and_get_reply(new_method_call(_portal(interface), method, signature, make_body(options)))
        if reply.header.message_type.name == "error":
            raise PortalError(f"{method}: {reply.body}")
        response, results = conn.recv_until_filtered(queue, timeout=timeout).body
    if response == 1:
        raise PortalError(f"{method}: pedido negado")
    if response != 0:
        raise PortalError(f"{method} falhou (código {response})")
    return results


def _create_session(conn: DBusConnection, interface: str) -> str:
    results = request(conn, interface, "CreateSession", "a{sv}", lambda opts: (opts,),
                      extra={"session_handle_token": ("s", _token())})
    return results["session_handle"][1]


class RemoteKeyboard:
    """Teclado virtual via portal RemoteDesktop.

    Na primeira vez o GNOME pergunta se o Fala pode controlar o teclado; o token de
    restauração salvo evita a pergunta nas próximas sessões.
    """

    DEVICE_KEYBOARD = 1
    PERSIST_UNTIL_REVOKED = 2
    TOKEN_PATH = STATE_DIR / "remote-desktop-token"

    def __init__(self):
        self._lock = threading.Lock()
        self._conn: DBusConnection | None = None
        self._session: str | None = None

    def ensure_session(self) -> None:
        """Abre a sessão (pode mostrar o diálogo de permissão e bloquear até a resposta)."""
        with self._lock:
            if self._session is None:
                self._start()

    def press(self, keycodes: list[int]) -> None:
        """Pressiona as teclas em ordem e solta na ordem inversa (ex.: Ctrl+V)."""
        with self._lock:
            for attempt in range(2):
                if self._session is None:
                    self._start()
                try:
                    for code in keycodes:
                        self._key(code, 1)
                    for code in reversed(keycodes):
                        self._key(code, 0)
                    return
                except Exception:
                    # Sessão encerrada (ex.: permissão revogada); recria uma vez.
                    self._reset()
                    if attempt:
                        raise

    def _key(self, keycode: int, state: int) -> None:
        msg = new_method_call(_portal("RemoteDesktop"), "NotifyKeyboardKeycode", "oa{sv}iu",
                              (self._session, {}, keycode, state))
        reply = self._conn.send_and_get_reply(msg, timeout=5)
        if reply.header.message_type.name == "error":
            raise PortalError(str(reply.body))

    def _reset(self) -> None:
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        self._session = None

    def _start(self) -> None:
        self._conn = connect()
        try:
            session = _create_session(self._conn, "RemoteDesktop")
            select = {"types": ("u", self.DEVICE_KEYBOARD), "persist_mode": ("u", self.PERSIST_UNTIL_REVOKED)}
            if self.TOKEN_PATH.exists():
                select["restore_token"] = ("s", self.TOKEN_PATH.read_text().strip())
            request(self._conn, "RemoteDesktop", "SelectDevices", "oa{sv}", lambda opts: (session, opts), extra=select)
            results = request(self._conn, "RemoteDesktop", "Start", "osa{sv}",
                              lambda opts: (session, "", opts), timeout=300)
            if "restore_token" in results:
                self.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
                self.TOKEN_PATH.write_text(results["restore_token"][1])
            self._session = session
        except Exception:
            self._reset()
            raise


class GlobalShortcut:
    """Atalho global via portal GlobalShortcuts, com eventos de apertar e soltar."""

    def __init__(self, shortcut_id: str, description: str, preferred_trigger: str,
                 on_press: Callable[[], None], on_release: Callable[[], None]):
        self._id = shortcut_id
        self._description = description
        self._trigger = preferred_trigger
        self._on_press = on_press
        self._on_release = on_release

    def run(self) -> None:
        """Registra o atalho e fica ouvindo para sempre (rode numa thread)."""
        conn = connect()
        session = _create_session(conn, "GlobalShortcuts")
        shortcuts = [(self._id, {"description": ("s", self._description),
                                 "preferred_trigger": ("s", self._trigger)})]
        # Na primeira vez o GNOME mostra um diálogo para confirmar (ou trocar) a tecla.
        request(conn, "GlobalShortcuts", "BindShortcuts", "oa(sa{sv})sa{sv}",
                lambda opts: (session, shortcuts, "", opts), timeout=300)

        rules = {
            member: MatchRule(type="signal", interface="org.freedesktop.portal.GlobalShortcuts",
                              member=member, path=DESKTOP_PATH)
            for member in ("Activated", "Deactivated")
        }
        proxy = Proxy(message_bus, conn)
        for rule in rules.values():
            proxy.AddMatch(rule)
        with conn.filter(rules["Activated"]) as pressed, conn.filter(rules["Deactivated"]) as released:
            while True:
                conn.recv_messages(timeout=None)
                for queue, callback in ((pressed, self._on_press), (released, self._on_release)):
                    while queue:
                        msg = queue.popleft()
                        if msg.body[0] == session and msg.body[1] == self._id:
                            callback()


def request_background(reason: str, commandline: list[str]) -> None:
    """Pede para rodar em segundo plano e iniciar com a sessão (no Flatpak)."""
    with connect() as conn:
        request(conn, "Background", "RequestBackground", "sa{sv}", lambda opts: ("", opts), timeout=300, extra={
            "reason": ("s", reason),
            "autostart": ("b", True),
            "commandline": ("as", commandline),
        })


def set_background_status(message: str) -> None:
    """Texto que o GNOME mostra na lista de apps em segundo plano."""
    with connect() as conn:
        conn.send_and_get_reply(new_method_call(_portal("Background"), "SetStatus", "a{sv}",
                                                ({"message": ("s", message)},)), timeout=5)
