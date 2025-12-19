from flask import Flask, request, jsonify, send_file
import os
from doc import generate_medical_pdf, populate_test_data
from DataBase.work_db import HospitalDBManager
app = Flask(__name__)


@app.route('/uzi/<id>/', methods=['GET'])
def handle_retrival(id):
    with HospitalDBManager() as db_manager:
        print("\nПоиск записей по vc:")
        results = db_manager.search_uzi_by_vc(id)
        for result in results:
            print(f"  - {result[3]} (Протокол: {result[2]}, Дата: {result[1]})")
        result=results[0]
        generate_medical_pdf(
            output_file="protocol.pdf",
            date=result[1],
            number_protocol=result[2],
            FIO=result[3],
            gender=result[4],
            date_birth=result[5],
            number_med_cart=result[6],
            nupr_otdel=result[7],
            vid_issled=result[8],
            vc_type=result[9],
            scaner=result[10],
            datchik=result[11],
            opisanie=result[12],
            zakl=result[13],
            fio_vrach=result[14],
            stamp_path = "seal.png"
        )
        return send_file("protocol.pdf") 
    return 500


if __name__ == '__main__':
    populate_test_data()
    app.run(port=9000, debug=True)
