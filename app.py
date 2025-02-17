from flask import Flask, render_template, request, jsonify, send_file
import os
from utils import extract_comp_plan_content, render_comp_plan_template, output_template_to_txt
import zipfile

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract", methods=["POST"])
def extract():
    try:
        if os.path.exists(UPLOAD_FOLDER):
            os.system(f"del /f /s /q {UPLOAD_FOLDER} 1>nul\nrmdir /s /q {UPLOAD_FOLDER}")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        files = request.files.getlist("files")
        if not files:
            return jsonify({'error': 'No JSON data received'}), 400

        saved_files = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            saved_files.append(file.filename)
        file_names = [os.path.join(UPLOAD_FOLDER, file_) for file_ in saved_files]
        converted_file_names = [file_name.replace(".pdf", ".txt") for file_name in saved_files]
        
        for file in file_names:
            comp_plan = extract_comp_plan_content(file)
            template = render_comp_plan_template(comp_plan)
            output_template_to_txt(template, file.replace(".pdf", ".txt"))

        return jsonify({"convertedFiles": converted_file_names, "download_dir": "/download"})

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route("/download")
def download_files():
    files = [file for file in os.listdir(UPLOAD_FOLDER) if file.endswith(".txt")]
    with zipfile.ZipFile(os.path.join(UPLOAD_FOLDER, "download.zip"), "w") as zip:
        for file in files:
            zip.write(os.path.join(UPLOAD_FOLDER, file), arcname=file)
    return send_file(os.path.join(UPLOAD_FOLDER, "download.zip"), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
