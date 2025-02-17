let fileObjs = [];
const uploadedFiles = document.querySelector(".uploaded-files");

function createFileElement(fileName, index) {
    // const fileContainer = document.querySelector(".file");
    const file = document.createElement("div");
    file.classList.add("file");
    file.innerHTML = `<p class="file-name">${fileName}<span class="cancel-button" data-index="${index}">X</span></p>`;
    return file;
}

window.addEventListener("load", () => {
    const input = document.getElementById("file-input");

    input.addEventListener("change", (e) => {
        const fileObj = e.target.files[0];
        if (!fileObj) return;

        let fileName = fileObj.name;
        fileObjs.push(fileObj);
        showFiles();
    });

    function showFiles() {
        const uploadFiles = document.querySelector(".uploaded-files");
        uploadFiles.innerHTML = "<h2 id='uploaded-files-title'>Uploaded Files</h2>"; // Clear previous files

        fileObjs.forEach((fileObj, index) => {
            const file = createFileElement(fileObj.name, index);
            uploadFiles.appendChild(file);
        });

        addCancelEventListeners();
    }

    function addCancelEventListeners() {
        document.querySelectorAll(".cancel-button").forEach((button) => {
            button.addEventListener("click", (e) => {
                const index = parseInt(e.target.dataset.index);
                fileObjs.splice(index, 1); // Remove the file from array
                showFiles(); // Re-render the file list
            });
        });
    }
});

function extractContent() {
    const formData = new FormData();
    const outputContainer = document.querySelector("#output-container");

    fileObjs.forEach((file) => {
        formData.append("files", file);
    });

    outputContainer.style.display = "none";

    fetch("/extract", {
        method: "POST",
        body: formData,
    })
        .then(response => response.json())
        .then(data => {
            const convertedFiles = document.querySelector(".files-ready-to-download");
            convertedFiles.innerHTML = ""; // Clear previous entries

            const convertedFileNames = data.convertedFiles;
            const downloadDir = data.download_dir;
            const downloadButton = document.querySelector("#download-button");

            outputContainer.style.display = "block";

            convertedFileNames.forEach((fileName) => {
                const file = createFileElement(fileName);
                convertedFiles.appendChild(file);
            });

            downloadButton.href = downloadDir;
        });
}
