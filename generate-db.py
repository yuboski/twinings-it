import sqlite3, json
import glob
from geopy.distance import geodesic


file_pattern = "results/result_*.json"
output_db = "db/twinings.db"
output_reports = "docs/reports"

generate = False
show_report = True

def get_cell_text(val):
    if isinstance(val, (int, float)):
        formatted = f"{val:,.0f}"
        formatted = formatted.replace(",", ".")
        return formatted
    else:
        return val

def save_rows_to_html(rows, cursor, filename):
    rows = [(i + 1, *row) for i, row in enumerate(rows)]
    col_names = ["#"] + [desc[0] for desc in cursor.description]
    reportname = filename.replace(output_reports + "/", "").replace(".html", "").replace("-", " ")
    html = "<table border='1'>\n"
    html += "  <tr><th class='title' colspan=" + str(len(col_names)) + ">" + reportname + "</th></tr>\n"
    html += "  <tr>" + "".join(f"<th>{col}</th>" for col in col_names) + "</tr>\n"
    for row in rows:
        html += "  <tr>" + "".join(f"<td>{get_cell_text(val)}</td>" for val in row) + "</tr>\n"
    html += "</table>"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)



conn = sqlite3.connect(output_db)
c = conn.cursor()

if generate:
    sql = """
        DROP TABLE IF EXISTS comuni
    """
    c.execute(sql)

    sql = """
        DROP TABLE IF EXISTS twins
    """
    c.execute(sql)

    sql = """
        CREATE TABLE IF NOT EXISTS comuni (id INTEGER PRIMARY KEY AUTOINCREMENT, 
        comune TEXT,
        lat REAL,
        log REAL, 
        stato TEXT,
        provincia TEXT,
        found_coords INTEGER,
        found_claims INTEGER)
    """
    c.execute(sql)

    conn.commit()

    sql = """
        CREATE TABLE IF NOT EXISTS twins (id INTEGER PRIMARY KEY AUTOINCREMENT, 
        idParent INTEGER,
        comune TEXT,
        lat REAL,
        log REAL, 
        distance REAL,
        stato TEXT,
        provincia TEXT,
        found_coords INTEGER,
        found_claims INTEGER)
    """
    c.execute(sql)

    conn.commit()
    
    for filename in glob.glob(file_pattern):
        with open(filename, "r", encoding="utf-8") as f:
            comuni = json.load(f)
            for comune in comuni:
                sql = """ INSERT INTO comuni (comune, lat, log, stato, provincia, found_coords, found_claims)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """
                c.execute(sql, (comune.get("comune"), comune.get("lat"), comune.get("log"), comune.get("stato"), comune.get("regione"), comune.get("found_coords"), comune.get("found_claims")))
                conn.commit()
                id_comune = c.lastrowid
                p1 = (comune.get("lat"), comune.get("log"))
                print(comune.get("comune"))
                for gemello in comune.get("gemelli"):
                    distance = None
                    if (gemello.get("lat") is not None and gemello.get("log") is not None):
                        p2 = (gemello.get("lat"), gemello.get("log"))
                        distance = geodesic(p1, p2).km

                    sql = """ INSERT INTO twins (comune, idParent, lat, log, distance, stato, provincia, found_coords, found_claims)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    c.execute(sql, (gemello.get("comune"), id_comune, gemello.get("lat"), gemello.get("log"), distance, gemello.get("stato"), gemello.get("regione"), gemello.get("found_coords"), gemello.get("found_claims")))
                    conn.commit()




if show_report:

    sql = """SELECT count(*) as comuni_total from comuni"""
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/count-comuni.html')

    sql = """SELECT count(*) as twins_total from twins"""
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/count-twins.html')

    sql = """SELECT ROW_NUMBER() OVER (ORDER BY round(T.distance)) AS "#", C.comune, C.provincia, T.comune as twin, T.stato, round(T.distance) as distance
    from comuni C inner join twins T on C.id = T.idParent 
    order by distance DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-distance.html')

    sql = """SELECT C.comune, C.provincia, T.comune as twin, T.provincia, round(T.distance) as distance
    from comuni C inner join twins T on C.id = T.idParent 
    where lower(T.stato) = 'italia'
    order by distance DESC
    limit 20

    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-distance-local.html')

    sql = """SELECT C.comune, C.provincia, count(T.id) as twins_count
    from comuni C inner join twins T on C.id = T.idParent 
    group by C.comune, C.provincia
    order by twins_count DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-twinings.html')

    sql = """SELECT case when T.stato = '' then 'not-found' else T.stato end as stato, count(T.id) as stati_count
    from twins T
    group by T.stato
    order by stati_count DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-twining-states.html')

    sql = """
    SELECT C.comune, T.stato, TT.stati_count from
    comuni C inner join twins T on C.id = T.idParent
    inner join (
        SELECT T.stato, count(T.id) as stati_count
        from twins T 
        group by T.stato
        having count(T.id)=1
        ) TT on T.stato = TT.stato
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/single-twin-states.html')





print()
print("-" * 80)
print ("TEMP QUERY")
print("-" * 80)
print()

sql = """    SELECT count(t.id) from twins T
where T.stato = ''
"""
c.execute(sql)
rows = c.fetchall()
print("-" * 100)
for row in rows:
    print(" ".join(f"{str(col):<20}" for col in row))






conn.close()






