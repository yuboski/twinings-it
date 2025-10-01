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
#        if tpl.name.strip() in ("Gemellaggio", "Gemellaggi"):
        if "gemellaggi" in tpl.name.strip().lower():
            # for param in tpl.params:
            #     value_code = mwparserfromhell.parse(str(param.value))
            #     links = value_code.filter_wikilinks()
            #     for link in links:
            #         link_title = str(link.title).strip()
            #         print(f"Parametro {param.name} → link: {link_title}")
            
            if tpl.has(2):
                comune = tpl.get(2).value.strip()  # parametro 1 = stato parametro 2 = Comune
                if tpl.has(1):
                    stato = tpl.get(1).value.strip()
                elif tpl.has('stato'):
                    stato = tpl.get('stato').value.strip()
                else:
                    stato = ""
                gemelli.append({"comune": comune, "stato": stato})
            else:
                if (tpl.has("città")):
                    comune = tpl.get("città").split("=")[-1].strip()
                    stato = ""
                    gemelli.append({"comune": comune, "stato": stato})
                else:
                    # TODO: HERE 
                    print(f"Template incompleto trovato: {tpl}")
    return gemelli


def get_comuni_lettera(lettera):
    letteraSearch = lettera
    if (lettera.upper() in ("H", "I", "J")):
        letteraSearch = "H-J"
    title = f"Comuni_d'Italia_({letteraSearch.upper()})"
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

def get_comune_real_name(title, stato, no_retry):
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{title}",
        "srlimit": 5,
        "format": "json"
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    data = r.json()

    return_title = title
    if data.get("query", {}).get("search"):
        return_title = data["query"]["search"][0]["title"]
        found_title = ''
        for result in data.get("query", {}).get("search", []):
            search_title = result.get("title", "")
            search_snippet = result.get("snippet", "")
            disambigua = "iniziano con o contengono il titolo".lower() in search_snippet.lower()
            if search_title.strip().lower() == title.strip().lower() and not found_title:
                found_title = search_title
            if search_title.lower().startswith(title.lower()) and stato.lower() in search_snippet.lower() and not disambigua and not found_title:
                found_title = search_title
                break
    if found_title:
        return_title = found_title
    if "(disambigua)" in return_title.lower():
        if no_retry:
            return_title = return_title.replace("(disambigua)", "").strip()
        else: 
            return_title = get_comune_real_name(f"{title} comune", stato, True)
    return return_title

def search_comune_properties(comune, search_gemelli, stato):
    comune_reaL_name = get_comune_real_name(comune, stato, False)
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
    for comuneObject in comuni:
        lat, lon, stato, regione, found_coords, found_claims, gemelli_properties = search_comune_properties(comuneObject.get("comune"), search_gemelli, comuneObject.get("stato"))
        comuni_properties.append({"comune": comuneObject.get("comune"), "lat": lat, "log": lon, "stato": stato, "regione": regione, "found_coords": found_coords, "found_claims": found_claims, "gemelli": gemelli_properties})
        print(f"\nComune: {comuneObject.get("comune")}")
        print(f"Coordinate: lat={lat}, lon={lon}")
        print(f"Stato: {stato}")
        print(f"Regione: {regione}")
        print(f"Found Coords: {found_coords}")
        print(f"Found Claims: {found_claims}")
        print(f"Gemelli: {gemelli_properties}")
    
    return comuni_properties

if __name__ == "__main__":
    
    #search_comune_properties("San Vito di Cadore", True, "Italia")

    #TODO: lista lettere da cercare
    #lettere = list(string.ascii_uppercase)
    lettere = list("STUVWXYZ")

    for lettera in lettere:
        comuni = get_comuni_lettera(lettera)
        print(f"Totale comuni con '{lettera}': {len(comuni)}")
        print("\n".join(comuni)) 
        comuni_objects = [{"comune": c, "stato": "Italia"} for c in comuni] 
        comuni_properties = search_comune_list(comuni_objects, True)

        filename = f"result_{lettera}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(comuni_properties, f, ensure_ascii=False, indent=4)

