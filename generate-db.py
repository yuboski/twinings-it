import sqlite3, json
import glob
from geopy.distance import geodesic


file_pattern = "results/result_*.json"
province_filename = "results/province.json"
output_db = "db/twinings.db"
output_reports = "docs/reports"

generate_db = False
generate_report = True

def get_cell_text(val):
    if isinstance(val, (int, float)):
        formatted = f"{val:,.0f}"
        formatted = formatted.replace(",", ".")
        return formatted
    else:
        return val

def save_rows_to_html(rows, cursor, filename, subtitle):
    rows = [(i + 1, *row) for i, row in enumerate(rows)]
    col_names = ["#"] + [desc[0] for desc in cursor.description]
    reportname = filename.replace(output_reports + "/", "").replace(".html", "").replace("-", " ")
    html = "<table border='1'>\n"
    html += "  <tr><th class='title' colspan=" + str(len(col_names)) + ">" + reportname + "</th></tr>\n"
    if subtitle: html += "  <tr><th class='title' colspan=" + str(len(col_names)) + ">" + subtitle + "</th></tr>\n"
    html += "  <tr>" + "".join(f"<th>{col}</th>" for col in col_names) + "</tr>\n"
    for row in rows:
        html += "  <tr>" + "".join(f"<td>{get_cell_text(val)}</td>" for val in row) + "</tr>\n"
    html += "</table>"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)



conn = sqlite3.connect(output_db)
c = conn.cursor()

if generate_db:
    sql = """
        DROP TABLE IF EXISTS comuni
    """
    c.execute(sql)

    sql = """
        DROP TABLE IF EXISTS twins
    """
    c.execute(sql)

    sql = """
        DROP TABLE IF EXISTS main_cities
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

    sql = """
        CREATE TABLE IF NOT EXISTS main_cities (name TEXT)
    """
    c.execute(sql)



    conn.commit()
    
    
    with open(province_filename, "r", encoding="utf-8") as f:
        province = json.load(f)
        for provincia in province:
                main_cities = provincia.get("nome").split("-")
                for main_city in main_cities:
                    sql = """ INSERT INTO main_cities (name)
                    VALUES(?)
                    """
                    c.execute(sql, (main_city.strip(),))
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




if generate_report:

    sql = """SELECT count(*) as comuni_total from comuni"""
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/count-comuni.html', '')

    sql = """SELECT count(*) as twins_total from twins"""
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/count-twins.html', '')

    sql = """SELECT C.comune || ', ' ||  C.provincia as comune, T.comune || ', ' ||  T.stato as twin, round(T.distance) as distance
    from comuni C inner join twins T on C.id = T.idParent 
    order by distance DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-distance.html', 'maggiore distanza tra comune e gemello internazionale')

    sql = """SELECT C.comune || ', ' || C.provincia as comune, T.comune || ', ' ||  T.provincia as twin, round(T.distance) as distance
    from comuni C inner join twins T on C.id = T.idParent 
    where lower(T.stato) = 'italia'
    order by distance DESC
    limit 20

    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-distance-local.html', 'maggiore distanza tra comune e gemello nazionale')

    sql = """SELECT C.comune || ', ' ||  C.provincia as comune, T.comune || ', ' ||  T.provincia as twin, round(T.distance) as distance
    from comuni C inner join twins T on C.id = T.idParent 
    where not distance is null and distance > 0
    order by distance ASC
    limit 20

    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-less-distance.html', 'minore distanza tra comune e gemello')

    sql = """SELECT C.comune, C.provincia, count(T.id) as twins_count
    from comuni C inner join twins T on C.id = T.idParent 
    group by C.comune, C.provincia
    order by twins_count DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-twinings.html', 'maggior numero di gemellaggi')

    sql = """SELECT case when T.stato = '' then 'not-found' else T.stato end as stato, count(T.id) as stati_count
    from twins T
    group by T.stato
    order by stati_count DESC
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-twining-states.html', 'maggior numero di stati gemellati')

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
    save_rows_to_html(rows, c, output_reports + '/single-twin-states.html', 'stati con un solo gemellaggio')

    sql = """
    SELECT T.comune ||  ', ' || T.stato as twin, count(T.idParent) as count_twinigs, GROUP_CONCAT(C.comune, "<br>") AS comuni from
    twins T inner join Comuni C on T.idParent = C.id
    group by T.comune || T.stato
    order by count_twinigs desc
    limit 20
    """
    c.execute(sql)
    rows = c.fetchall()
    save_rows_to_html(rows, c, output_reports + '/top-20-twining-cities.html', 'città gemellata con più comuni')




print()
print("-" * 80)
print ("TEMP QUERY")
print("-" * 80)
print()






sql = """SELECT C.comune, T.* from twins T
inner join comuni C  on C.id = T.idParent
where T.stato is null or T.stato = ''
"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/twin-without-state.html', '')


sql = """SELECT count(T.id) from twins T
inner join comuni C  on C.id = T.idParent
where T.stato is null or T.stato = ''
"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/count-twin-without-state.html', '')


sql = """SELECT C.comune, T.* from twins T
inner join comuni C  on C.id = T.idParent
where T.lat is null or T.log is null
"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/twin-without-coords.html', '')

sql = """SELECT count(T.id) from twins T
inner join comuni C  on C.id = T.idParent
where T.lat is null or T.log is null
"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/count-twin-without-coords.html', '')

sql = """
select 'without', (
    SELECT count(C.id) from comuni C
    LEFT join twins T on C.id = T.idParent
    where T.id is null) as count
union
select 'with', (
    SELECT count(C.id) from comuni C
    INNER join twins T on C.id = T.idParent) as count
"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/count-comuni-without-twins.html', '')




sql = """
SELECT MC.name, C.* from main_cities MC left join
comuni C on lower(C.comune) LIKE '%' || lower(MC.name) || '%'
where C.id is null


"""
c.execute(sql)
rows = c.fetchall()
save_rows_to_html(rows, c, output_reports + '/main_cities_without_data.html', '')
print("-" * 100)
for row in rows:
    print(" ".join(f"{str(col):<20}" for col in row))



conn.close()






