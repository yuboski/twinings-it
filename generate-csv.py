import glob
import json
import csv

file_pattern = "results/result_*.json"
output_csv = "docs/data/twinings.csv"
output_fails_csv = "docs/data/twinings_fails.csv"


fieldnames = [
    "comune_start_id",
    "comune_start_name",
    "comune_start_lat",
    "comune_start_log",
    "comune_start_regione",
    "comune_end_id",
    "comune_end_name",
    "comune_end_lat",
    "comune_end_log",
    "comune_end_stato",
    "comune_end_found_coords",
    "comune_end_found_claims",
    "gemelli_names"
]

failedTwins = []


with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='|')
    writer.writeheader()

    for filename in glob.glob(file_pattern):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            

            for start in data:
                start_name = start.get("comune")
                start_lat = start.get("lat")
                start_log = start.get("log")
                start_regione = start.get("regione")
                gemelli_names = ', '.join([f'{g["comune"]} ({g["stato"]})' for g in start.get("gemelli", [])])
                

                for end in start.get("gemelli", []):
                    row = {
                        "comune_start_id": f"s_{start_name}",
                        "comune_start_name": start_name,
                        "comune_start_lat": start_lat,
                        "comune_start_log": start_log,
                        "comune_start_regione": start_regione,
                        "comune_end_id": f"e_{end.get("comune")}",
                        "comune_end_name": end.get("comune"),
                        "comune_end_lat": end.get("lat"),
                        "comune_end_log": end.get("log"),
                        "comune_end_stato": end.get("stato"),
                        "comune_end_found_coords": end.get("found_coords"),
                        "comune_end_found_claims": end.get("found_claims"),
                        "gemelli_names": gemelli_names
                    }
                    if end.get("found_coords") and end.get("found_claims"):
                        writer.writerow(row)
                    else:
                        failedTwins.append(row)


print(f"CSV generato: {output_csv}")

with open(output_fails_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for item in failedTwins:
        writer.writerow(item)

print(f"CSV fails generato: {output_fails_csv}")