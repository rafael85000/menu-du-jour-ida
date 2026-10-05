"""
Robot Trattoria Ida : poste le menu du jour en story Instagram.

1. Cherche dans Gmail le mail du jour "menu" venant de ida.trattoria.direction@gmail.com
2. Recupere la piece jointe JPG, garde un seul exemplaire du menu, format story 1080x1920
3. Depose l'image dans le depot GitHub (Instagram doit pouvoir la telecharger)
4. Publie la story (API officielle Meta, "Instagram API with Instagram Login")
5. Met le libelle "Story postee" sur le mail pour ne jamais poster deux fois

Secrets GitHub necessaires :
  GMAIL_ADRESSE        rafaelcolonnello85@gmail.com
  GMAIL_MOT_DE_PASSE   mot de passe d'application Google (16 lettres)
  IG_TOKEN             jeton Instagram longue duree
"""
import email
import imaplib
import os
import subprocess
import sys
import time
from datetime import datetime
from email.header import decode_header
from zoneinfo import ZoneInfo

import requests

from rogner import rogner_story

EXPEDITEUR = "ida.trattoria.direction@gmail.com"
OBJET = "menu"
LIBELLE = "StoryPostee"
API = "https://graph.instagram.com/v23.0"
PARIS = ZoneInfo("Europe/Paris")


def texte(h):
    out = []
    for val, enc in decode_header(h or ""):
        out.append(val.decode(enc or "utf-8", "replace") if isinstance(val, bytes) else val)
    return "".join(out)


def chercher_mail_du_jour(imap):
    imap.select("INBOX")
    depuis = datetime.now(PARIS).strftime("%d-%b-%Y")
    requete = f'from:{EXPEDITEUR} subject:"{OBJET}" -label:{LIBELLE}'
    typ, data = imap.search(None, "SINCE", depuis, "X-GM-RAW", '"' + requete.replace('"', '\\"') + '"')
    ids = data[0].split() if typ == "OK" else []
    return ids[-1] if ids else None


def extraire_jpg(msg):
    for part in msg.walk():
        nom = texte(part.get_filename() or "").lower()
        if part.get_content_type() in ("image/jpeg", "image/jpg") or nom.endswith((".jpg", ".jpeg")):
            return part.get_payload(decode=True)
    return None


def rendre_public(chemin):
    """Commit + push de l'image ; renvoie son adresse publique."""
    run = lambda *c: subprocess.run(c, check=True)
    run("git", "config", "user.name", "robot-menu")
    run("git", "config", "user.email", "robot-menu@users.noreply.github.com")
    run("git", "add", chemin)
    run("git", "commit", "-m", f"Menu du jour {chemin}")
    run("git", "push")
    depot = os.environ["GITHUB_REPOSITORY"]
    branche = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{depot}/{branche}/{chemin}"


def publier_story(url_image, token):
    r = requests.post(f"{API}/me/media", data={
        "image_url": url_image, "media_type": "STORIES", "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram (creation) : {r.text}")
    conteneur = r.json()["id"]
    for _ in range(24):  # Instagram telecharge l'image, on attend qu'il ait fini
        s = requests.get(f"{API}/{conteneur}", params={
            "fields": "status_code", "access_token": token}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram refuse l'image : {s}")
        time.sleep(5)
    r = requests.post(f"{API}/me/media_publish", data={
        "creation_id": conteneur, "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram (publication) : {r.text}")
    return r.json()["id"]


def main():
    heure = datetime.now(PARIS).hour
    if not (7 <= heure < 13):
        print("En dehors de 7h-13h (heure de Paris), rien a faire.")
        return
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(os.environ["GMAIL_ADRESSE"], os.environ["GMAIL_MOT_DE_PASSE"])
    num = chercher_mail_du_jour(imap)
    if not num:
        print("Pas de nouveau menu pour l'instant.")
        return

    _, data = imap.fetch(num, "(RFC822)")
    jpg = extraire_jpg(email.message_from_bytes(data[0][1]))
    if not jpg:
        raise RuntimeError("Mail 'menu' trouve, mais sans image JPG.")

    jour = datetime.now(PARIS).strftime("%Y-%m-%d_%H%M")
    os.makedirs("stories", exist_ok=True)
    brut, story = f"/tmp/menu_{jour}.jpg", f"stories/story_{jour}.jpg"
    with open(brut, "wb") as f:
        f.write(jpg)
    rogner_story(brut, story)

    url = rendre_public(story)
    time.sleep(20)  # laisser le temps a GitHub de mettre l'image en ligne
    media_id = publier_story(url, os.environ["IG_TOKEN"])
    print(f"Story publiee (id {media_id}) a partir de {url}")

    imap.store(num, "+X-GM-LABELS", f'"{LIBELLE}"')
    imap.logout()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(1)  # GitHub envoie alors un mail d'alerte automatiquement
