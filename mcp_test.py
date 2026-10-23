"""End-to-end-Test des Kommandozentrale-MCP über stdio (so startet ihn auch Claude Code).

Voraussetzung: der Server läuft (python server.py). Aufruf: python mcp_test.py
Der Test ändert nur den Demo-Eintrag „skript-wochenplan“ und setzt alles wieder zurück.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HIER = Path(__file__).resolve().parent
TEST_ID = "skript-wochenplan"


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(HIER / "mcp_server.py")],
                                    env=dict(os.environ))   # CCC_PORT usw. weitergeben
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print(f"WERKZEUGE ({len(tools)}):", ", ".join(t.name for t in tools))

            async def call(name, **args):
                res = await s.call_tool(name, args)
                txt = "".join(getattr(c, "text", "") for c in res.content)
                if res.is_error:
                    raise RuntimeError(f"{name}: {txt}")
                sc = res.structured_content
                if sc is not None:
                    return json.dumps(sc["result"] if set(sc) == {"result"} else sc)
                return txt

            ue = json.loads(await call("board_uebersicht"))
            print("JE STUFE:", ue["je_stufe"], "| ideen", ue["ideen"])
            print("SCHNITT-AUFTRÄGE:", [a["id"] for a in json.loads(await call("schnitt_auftraege") or "[]")])

            print(await call("einplanen", video_id=TEST_ID, zeit="2026-01-01T18:00", plattformen=["tiktok"]))
            faellig = [f["id"] for f in json.loads(await call("faellige_uploads") or "[]")]
            print("FÄLLIG:", faellig)
            assert TEST_ID in faellig, "Termin in der Vergangenheit muss fällig sein"
            print(await call("termin_loeschen", video_id=TEST_ID))

            name = json.loads(await call("video_details", video_id=TEST_ID))["texte"][0]["name"]
            print(await call("text_bearbeiten", video_id=TEST_ID, textname=name, neuer_text="MCP-TEST"))
            t = json.loads(await call("video_details", video_id=TEST_ID))["texte"][0]
            assert t["text"] == "MCP-TEST" and t["bearbeitet"]
            print(await call("text_zuruecksetzen", video_id=TEST_ID, textname=name))

            try:
                await call("video_details", video_id="gibts-nicht")
                raise AssertionError("Fehlerfall wurde nicht erkannt")
            except RuntimeError as e:
                print("FEHLERFALL OK:", str(e)[:70])
            print("\nALLES OK")


asyncio.run(main())
