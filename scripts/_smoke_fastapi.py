"""Wegwerp-smoke: login + hoofdroutes per rol via TestClient. Verwijderen na gebruik."""

from fastapi.testclient import TestClient

from app_fastapi.main import app

STUDENT = "100005"
MENTOR = "D. Hendriks"
PW = "Welkom123"

STUDENT_ROUTES = ["/home", "/voortgang", "/leercoach", "/welzijn", "/groeidossier"]
DOCENT_ROUTES = ["/home", "/groep", "/outreach", "/groeidossier"]


def _login(client: TestClient, rol: str, ident: str) -> None:
    r = client.post(
        "/login",
        data={"rol": rol, "identifier": ident, "wachtwoord": PW},
        follow_redirects=False,
    )
    assert r.status_code == 303, f"login {rol} → {r.status_code}"
    assert r.headers["location"] == "/home", f"login {rol} redirect → {r.headers['location']}"


def _check(rol: str, ident: str, routes: list[str]) -> None:
    with TestClient(app) as client:
        _login(client, rol, ident)
        for route in routes:
            r = client.get(route)
            status = "OK " if r.status_code == 200 else "FAIL"
            print(f"  [{status}] {rol:7} GET {route} → {r.status_code}")
            assert r.status_code == 200, f"{rol} {route} → {r.status_code}"


if __name__ == "__main__":
    print("== student ==")
    _check("student", STUDENT, STUDENT_ROUTES)
    print("== docent ==")
    _check("docent", MENTOR, DOCENT_ROUTES)
    print("ALLE ROUTES 200 ✓")
