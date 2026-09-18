const socket = io();

let currentJobId = null;


// ============================================================
// SOCKET.IO CONNECTION
// ============================================================

socket.on("connect", function () {
    console.log("Connected to Flask Socket.IO");
});

socket.on("disconnect", function () {
    console.log("Disconnected from Flask Socket.IO");
});


// ============================================================
// REALTIME ANSIBLE LOGS
// ============================================================

socket.on("ansible_log", function (data) {

    // Ignore logs from another job
    if (currentJobId && data.job_id !== currentJobId) {
        return;
    }

    const output = document.getElementById("output");

    // Remove initial message
    if (
        output.textContent === "No output yet." ||
        output.textContent === "Starting Ansible...\n"
    ) {
        output.textContent = "";
    }

    output.textContent += data.line + "\n";

    // Scroll to latest log
    output.scrollTop = output.scrollHeight;
});


// ============================================================
// JOB STATUS
// ============================================================

socket.on("job_status", function (data) {

    console.log("Job status received:", data);

    // Ignore another job
    if (currentJobId && data.job_id !== currentJobId) {
        return;
    }

    const status = document.getElementById("status");
    const output = document.getElementById("output");
    const runButton = document.getElementById("runButton");


    // RUNNING
    if (data.status === "RUNNING") {

        status.className = "status running";

        status.textContent =
            "⏳ Ansible job is running...";

        return;
    }


    // SUCCESS
    if (data.status === "SUCCESS") {

        status.className = "status success";

        status.textContent =
            "✅ Ansible execution completed successfully.";

        output.textContent +=
            "\n\n========== SUCCESS ==========\n";

        runButton.disabled = false;

        return;
    }


    // FAILED
    if (data.status === "FAILED") {

        status.className = "status failed";

        status.textContent =
            "❌ Ansible execution failed.";

        output.textContent +=
            "\n\n========== FAILED ==========\n";

        runButton.disabled = false;

        return;
    }


    // ERROR
    if (data.status === "ERROR") {

        status.className = "status failed";

        status.textContent =
            "❌ Error: " +
            (data.message || "Unknown error");

        output.textContent +=
            "\n\n========== ERROR ==========\n";

        runButton.disabled = false;

        return;
    }
});


// ============================================================
// LOAD PLAYBOOKS
// ============================================================

async function loadPlaybooks() {

    try {

        const response =
            await fetch("/api/playbooks");

        const result =
            await response.json();

        console.log("Playbooks:", result);

        const playbookSelect =
            document.getElementById("playbook");

        playbookSelect.innerHTML = "";


        result.forEach(function (playbook) {

            const option =
                document.createElement("option");

            option.value = playbook;

            option.textContent = playbook;

            playbookSelect.appendChild(option);
        });


    } catch (error) {

        console.error(
            "Error loading playbooks:",
            error
        );
    }
}


// ============================================================
// LOAD INVENTORIES
// ============================================================

async function loadInventories() {

    try {

        const response =
            await fetch("/api/inventories");

        const result =
            await response.json();

        console.log("Inventories:", result);

        const inventorySelect =
            document.getElementById("inventory");

        inventorySelect.innerHTML = "";


        result.forEach(function (inventory) {

            const option =
                document.createElement("option");

            option.value = inventory;

            option.textContent = inventory;

            inventorySelect.appendChild(option);
        });


    } catch (error) {

        console.error(
            "Error loading inventories:",
            error
        );
    }
}


// ============================================================
// RUN PLAYBOOK
// ============================================================

async function runPlaybook() {

    const playbook =
        document.getElementById("playbook").value;

    const inventory =
        document.getElementById("inventory").value;

    const extraVars =
        document.getElementById("extraVars").value;

    const output =
        document.getElementById("output");

    const status =
        document.getElementById("status");

    const command =
        document.getElementById("command");

    const runButton =
        document.getElementById("runButton");


    // --------------------------------------------------------
    // Reset UI
    // --------------------------------------------------------

    currentJobId = null;

    output.textContent =
        "Starting Ansible...\n";

    status.className =
        "status running";

    status.textContent =
        "⏳ Starting Ansible job...";

    command.textContent =
        "Preparing command...";

    runButton.disabled = true;


    // --------------------------------------------------------
    // Send request to Flask
    // --------------------------------------------------------

    try {

        const response =
            await fetch("/api/run", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    playbook: playbook,

                    inventory: inventory,

                    extra_vars: extraVars
                })
            });


        const result =
            await response.json();


        console.log(
            "Run API response:",
            result
        );


        // ----------------------------------------------------
        // Backend rejected request
        // ----------------------------------------------------

        if (!response.ok) {

            status.className =
                "status failed";

            status.textContent =
                "❌ Failed to start Ansible.";

            output.textContent +=
                "\n" +
                (result.message ||
                 "Backend returned an error.");

            runButton.disabled = false;

            return;
        }


        // ----------------------------------------------------
        // Save Job ID
        // ----------------------------------------------------

        currentJobId =
            result.job_id;


        // ----------------------------------------------------
        // Display Job ID
        // ----------------------------------------------------

        output.textContent +=
            "\nJob ID: " +
            currentJobId +
            "\n";


        // ----------------------------------------------------
        // Display command
        // ----------------------------------------------------

        if (result.command) {

            command.textContent =
                result.command;
        }


        // ----------------------------------------------------
        // Job created
        // ----------------------------------------------------

        status.className =
            "status running";

        status.textContent =
            "⏳ Ansible job started...";


    } catch (error) {

        console.error(error);

        status.className =
            "status failed";

        status.textContent =
            "❌ Could not communicate with backend.";

        output.textContent +=
            "\n" + error;

        runButton.disabled = false;
    }
}


// ============================================================
// PAGE LOAD
// ============================================================

loadPlaybooks();

loadInventories();