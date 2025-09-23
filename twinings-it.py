import requests
import re
import mwparserfromhell
import json
import string


HEADERS = {"User-Agent": "MyWikiApp/1.0 (https://example.com; myemail@example.com)"}
WIKI_API = "https://it.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"

def get_coordinates(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "coordinates",
        "format": "json"
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    for page in pages.values():
        coords = page.get("coordinates")
        if coords:
            return coords[0]["lat"], coords[0]["lon"], True
    # TODO: HERE 
    return None, None, False

def get_wikibase_item(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageprops",
        "format": "json"
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    for page in pages.values():
        if "pageprops" in page and "wikibase_item" in page["pageprops"]:
            return page["pageprops"]["wikibase_item"]
    # TODO: HERE 
    return None

def get_wikidata_claims(qid):
    url = WIKIDATA_API.format(qid)
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    claims = r.json()["entities"][qid]["claims"]

    def get_label(prop_id):
        try:
            value_qid = claims[prop_id][0]["mainsnak"]["datavalue"]["value"]["id"]
            # recupera il nome leggibile in italiano
            url_label = WIKIDATA_API.format(value_qid)
            r_label = requests.get(url_label, headers=HEADERS, timeout=10)
            r_label.raise_for_status()
            label_data = r_label.json()
            return label_data["entities"][value_qid]["labels"]["it"]["value"]
        except:
            # TODO: HERE 
            return ""
    
    stato = get_label("P17")   # Stato
    regione = get_label("P131")  # Regione / entità superiore
    return stato, regione

def get_gemellaggi(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json"
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    page = next(iter(pages.values()))
    wikitext = page["revisions"][0]["*"]

    wikicode = mwparserfromhell.parse(wikitext)
    gemelli = []

    # Cerca tutti i template {{Gemellaggio|Paese|Comune|...}}
    for tpl in wikicode.filter_templates():
        if tpl.name.strip() == "Gemellaggio":
            if tpl.has(2):
                comune = tpl.get(2).value.strip()  # parametro 2 = Comune
                gemelli.append(comune)
            else:
                if (tpl.has("città")):
                    comune = tpl.get("città").split("=")[-1].strip()
                    gemelli.append(comune)
                else:
                    # TODO: HERE 
                    print(f"Template incompleto trovato: {tpl}")
    return gemelli


def get_comuni_lettera(lettera):
    title = f"Comuni_d'Italia_({lettera.upper()})"
    params = {
        "action": "query",
        "titles": title,
        "prop": "links",
        "pllimit": "max",
        "format": "json"
    }

    comuni = []
    while True:
        r = requests.get(WIKI_API, params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        pages = data["query"]["pages"]
        for page in pages.values():
            links = page.get("links", [])
            for link in links:
                if link["title"].startswith(lettera):
                    comuni.append(link["title"])
        # Controlla se ci sono più pagine (continue)
        if "continue" in data:
            params.update(data["continue"])
        else:
            break
    return comuni

def get_comune_real_name(title):
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{title} comune",
        "srlimit": 1,
        "format": "json"
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    data = r.json()

    if data["query"]["search"]:
        title = data["query"]["search"][0]["title"]

    return title

def search_comune_properties(comune, search_gemelli):
    comune_reaL_name = get_comune_real_name(comune)
    lat, lon, found_coords = get_coordinates(comune_reaL_name)
    qid = get_wikibase_item(comune_reaL_name)
    if qid:
        stato, regione = get_wikidata_claims(qid)
        found_claims = True
    else:
        # TODO: HERE 
        stato, regione = "", ""
        found_claims = True
    
    
    gemelli = get_gemellaggi(comune_reaL_name) if search_gemelli else []
    gemelli_properties = search_comune_list(gemelli, False) if search_gemelli else []

    return lat, lon, stato, regione, found_coords, found_claims, gemelli_properties


def search_comune_list(comuni, search_gemelli):
    comuni_properties = []
    for comune in comuni:
        lat, lon, stato, regione, found_coords, found_claims, gemelli_properties = search_comune_properties(comune, search_gemelli)
        comuni_properties.append({"comune": comune, "lat": lat, "log": lon, "stato": stato, "regione": regione, "found_coords": found_coords, "found_claims": found_claims, "gemelli": gemelli_properties})
        print(f"\nComune: {comune}")
        print(f"Coordinate: lat={lat}, lon={lon}")
        print(f"Stato: {stato}")
        print(f"Regione: {regione}")
        print(f"Found Coords: {found_coords}")
        print(f"Found Claims: {found_claims}")
        print(f"Gemelli: {gemelli_properties}")
    
    return comuni_properties

if __name__ == "__main__":
    
    #search_comune_properties("Torre Pellice", True)

    #TODO: lista lettere da cercare
    lettere = list(string.ascii_uppercase)
    #lettere = list("TUVWXYZ")

    for lettera in lettere:
        comuni = get_comuni_lettera(lettera)
        print(f"Totale comuni con '{lettera}': {len(comuni)}")
        print("\n".join(comuni))  
        comuni_properties = search_comune_list(comuni, True)

        filename = f"result_{lettera}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(comuni_properties, f, ensure_ascii=False, indent=4)

