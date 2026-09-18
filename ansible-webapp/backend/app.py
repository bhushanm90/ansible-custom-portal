from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from pathlib import Path
import subprocess
import shlex
import threading
import uuid
import sqlite3


# ==================================================
# Application configuration
# ==================================================

app = Flask(__name__)

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)


# ==================================================
# Directory configuration
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"
PLAYBOOK_DIR = BASE_DIR / "ansible" / "playbooks"
INVENTORY_DIR = BASE_DIR / "ansible" / "inventory"

DB_FILE = BASE_DIR / "backend" / "jobs.db"


# ==================================================
# Job storage
#
# Temporary in-memory storage.
# SQLite database is also used for persistence.
# ==================================================

jobs = {}


# ==================================================
# Database
# ==================================================

def get_db_connection():

    connection = sqlite3.connect(DB_FILE)

    connection.row_factory = sqlite3.Row

    return connection


# ==================================================
# Serve frontend
# ==================================================

@app.route("/")
def index():

    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


@app.route("/<path:filename>")
def frontend_files(filename):

    return send_from_directory(
        FRONTEND_DIR,
        filename
    )


# ==================================================
# Get available playbooks
# ==================================================

@app.route("/api/playbooks", methods=["GET"])
def get_playbooks():

    playbooks = sorted(
        [
            file.name
            for file in PLAYBOOK_DIR.glob("*.yml")
        ]
        +
        [
            file.name
            for file in PLAYBOOK_DIR.glob("*.yaml")
        ]
    )

    return jsonify(playbooks)


# ==================================================
# Get available inventories
# ==================================================

@app.route("/api/inventories", methods=["GET"])
def get_inventories():

    inventories = sorted(
        [
            file.name
            for file in INVENTORY_DIR.glob("*.ini")
        ]
        +
        [
            file.name
            for file in INVENTORY_DIR.glob("*.yml")
        ]
        +
        [
            file.name
            for file in INVENTORY_DIR.glob("*.yaml")
        ]
    )

    return jsonify(inventories)


# ==================================================
# Background Ansible Job
# ==================================================

# ==================================================
# Background Ansible Job
# ==================================================

def execute_ansible_job(
    job_id,
    command
):

    # ------------------------------------------------
    # Update job status in memory
    # ------------------------------------------------

    jobs[job_id]["status"] = "RUNNING"

    # ------------------------------------------------
    # Update job status in SQLite
    # ------------------------------------------------

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE jobs
        SET status = ?
        WHERE job_id = ?
        """,
        (
            "RUNNING",
            job_id
        )
    )

    connection.commit()
    connection.close()

    # ------------------------------------------------
    # Send RUNNING status to browser
    # ------------------------------------------------

    socketio.emit(
        "job_status",
        {
            "job_id": job_id,
            "status": "RUNNING"
        }
    )

    # =================================================
    # Try to execute Ansible
    # =================================================

    try:

        # --------------------------------------------
        # Start Ansible
        # --------------------------------------------

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # --------------------------------------------
        # Store process object in memory
        # --------------------------------------------

        jobs[job_id]["process"] = process

        output_lines = []

        # --------------------------------------------
        # Read Ansible output line-by-line
        # --------------------------------------------

        for line in process.stdout:

            line = line.rstrip()

            print(
                f"[{job_id}] {line}",
                flush=True
            )

            output_lines.append(line)

            # ----------------------------------------
            # Store log in memory
            # ----------------------------------------

            jobs[job_id]["logs"].append(line)

            # ----------------------------------------
            # Send realtime log to browser
            # ----------------------------------------

            socketio.emit(
                "ansible_log",
                {
                    "job_id": job_id,
                    "line": line
                }
            )

        # --------------------------------------------
        # Wait for process to finish
        # --------------------------------------------

        process.wait()

        # --------------------------------------------
        # Save final output in memory
        # --------------------------------------------

        jobs[job_id]["return_code"] = process.returncode

        jobs[job_id]["output"] = "\n".join(output_lines)

        # --------------------------------------------
        # Determine final status
        # --------------------------------------------

        if process.returncode == 0:

            jobs[job_id]["status"] = "SUCCESS"

        else:

            jobs[job_id]["status"] = "FAILED"

        # --------------------------------------------
        # Update final result in SQLite
        # --------------------------------------------

        connection = get_db_connection()

        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                return_code = ?,
                output = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (
                jobs[job_id]["status"],
                process.returncode,
                jobs[job_id]["output"],
                job_id
            )
        )

        connection.commit()
        connection.close()

        # --------------------------------------------
        # Send final status to browser
        # --------------------------------------------

        socketio.emit(
            "job_status",
            {
                "job_id": job_id,
                "status": jobs[job_id]["status"],
                "return_code": process.returncode
            }
        )

    # =================================================
    # Ansible command not found
    # =================================================

    except FileNotFoundError:

        jobs[job_id]["status"] = "ERROR"

        jobs[job_id]["message"] = (
            "ansible-playbook command not found. "
            "Is Ansible installed?"
        )

        # --------------------------------------------
        # Save error to SQLite
        # --------------------------------------------

        connection = get_db_connection()

        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                output = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (
                "ERROR",
                jobs[job_id]["message"],
                job_id
            )
        )

        connection.commit()
        connection.close()

        # --------------------------------------------
        # Send error to browser
        # --------------------------------------------

        socketio.emit(
            "job_status",
            {
                "job_id": job_id,
                "status": "ERROR",
                "message": jobs[job_id]["message"]
            }
        )

    # =================================================
    # Other unexpected errors
    # =================================================

    except Exception as error:

        jobs[job_id]["status"] = "ERROR"

        jobs[job_id]["message"] = str(error)

        # --------------------------------------------
        # Save error to SQLite
        # --------------------------------------------

        connection = get_db_connection()

        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                output = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (
                "ERROR",
                str(error),
                job_id
            )
        )

        connection.commit()
        connection.close()

        # --------------------------------------------
        # Send error to browser
        # --------------------------------------------

        socketio.emit(
            "job_status",
            {
                "job_id": job_id,
                "status": "ERROR",
                "message": str(error)
            }
        )

    # =================================================
    # Other execution errors
    # =================================================

    except Exception as error:

     jobs[job_id]["status"] = "ERROR"
 
     jobs[job_id]["message"] = str(error)

    # --------------------------------------------
    # Save error to SQLite
    # --------------------------------------------

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE jobs
        SET
            status = ?,
            output = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE job_id = ?
        """,
        (
            "ERROR",
            str(error),
            job_id
        )
    )

    connection.commit()
    connection.close()

    # --------------------------------------------
    # Send error to browser
    # --------------------------------------------

    socketio.emit(
        "job_status",
        {
            "job_id": job_id,
            "status": "ERROR",
            "message": str(error)
        }
    )

# ==================================================
# Start Ansible Job
# ==================================================

@app.route("/api/run", methods=["POST"])
def run_playbook():

    data = request.get_json()

    # ------------------------------------------------
    # Validate request
    # ------------------------------------------------

    if not data:

        return jsonify({

            "success": False,

            "message":
                "No data received"

        }), 400

    # ------------------------------------------------
    # Get input values
    # ------------------------------------------------

    playbook = data.get("playbook")

    inventory = data.get("inventory")

    extra_vars = data.get(
        "extra_vars",
        ""
    )

    # ------------------------------------------------
    # Validate playbook
    # ------------------------------------------------

    if not playbook:

        return jsonify({

            "success": False,

            "message":
                "Please select a playbook"

        }), 400

    # ------------------------------------------------
    # Validate inventory
    # ------------------------------------------------

    if not inventory:

        return jsonify({

            "success": False,

            "message":
                "Please select an inventory"

        }), 400

    # ------------------------------------------------
    # Build absolute paths
    # ------------------------------------------------

    playbook_path = (
        PLAYBOOK_DIR / playbook
    ).resolve()

    inventory_path = (
        INVENTORY_DIR / inventory
    ).resolve()

    # ------------------------------------------------
    # Security validation
    # ------------------------------------------------

    if PLAYBOOK_DIR.resolve() \
            not in playbook_path.parents:

        return jsonify({

            "success": False,

            "message":
                "Invalid playbook"

        }), 400

    if INVENTORY_DIR.resolve() \
            not in inventory_path.parents:

        return jsonify({

            "success": False,

            "message":
                "Invalid inventory"

        }), 400

    # ------------------------------------------------
    # Check playbook file
    # ------------------------------------------------

    if not playbook_path.is_file():

        return jsonify({

            "success": False,

            "message":
                "Playbook not found"

        }), 404

    # ------------------------------------------------
    # Check inventory file
    # ------------------------------------------------

    if not inventory_path.is_file():

        return jsonify({

            "success": False,

            "message":
                "Inventory not found"

        }), 404

    # ------------------------------------------------
    # Build Ansible command
    # ------------------------------------------------

    command = [

        "ansible-playbook",

        "-i",

        str(inventory_path),

        str(playbook_path)

    ]

    # ------------------------------------------------
    # Add extra variables
    # ------------------------------------------------

    if extra_vars.strip():

        command.extend([

            "-e",

            extra_vars

        ])

    # =================================================
    # Create unique Job ID
    # =================================================

    job_id = str(
        uuid.uuid4()
    )

    # =================================================
    # Create job record in memory
    # =================================================

    jobs[job_id] = {

        "job_id":
            job_id,

        "status":
            "PENDING",

        "playbook":
            playbook,

        "inventory":
            inventory,

        "extra_vars":
            extra_vars,

        "command":
            " ".join(

                shlex.quote(part)

                for part in command

            ),

        "logs":
            [],

        "output":
            "",

        "return_code":
            None

    }

    # =================================================
    # Save job to SQLite database
    # =================================================

    connection = get_db_connection()

    connection.execute(

        """
        INSERT INTO jobs (
            job_id,
            status,
            playbook,
            inventory,
            extra_vars,
            command,
            return_code,
            output
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,

        (

            job_id,

            "PENDING",

            playbook,

            inventory,

            extra_vars,

            jobs[job_id]["command"],

            None,

            ""

        )

    )

    connection.commit()

    connection.close()

    # =================================================
    # Start background thread
    # =================================================

    thread = threading.Thread(

        target=execute_ansible_job,

        args=(
            job_id,
            command
        )

    )

    thread.daemon = True

    thread.start()

    # =================================================
    # Return immediately to browser
    # =================================================

    return jsonify({

        "success":
            True,

        "job_id":
            job_id,

        "status":
            "PENDING",

        "message":
            "Ansible job started",

        "command":
            jobs[job_id]["command"]

    })


# ==================================================
# Get Job Status
# ==================================================

@app.route(
    "/api/jobs/<job_id>",
    methods=["GET"]
)
def get_job(job_id):

    job = jobs.get(job_id)

    # ------------------------------------------------
    # Job not found
    # ------------------------------------------------

    if not job:

        return jsonify({

            "success": False,

            "message":
                "Job not found"

        }), 404

    # ------------------------------------------------
    # Don't send process object to browser
    # ------------------------------------------------

    response = {

        "job_id":
            job["job_id"],

        "status":
            job["status"],

        "playbook":
            job["playbook"],

        "inventory":
            job["inventory"],

        "command":
            job["command"],

        "return_code":
            job["return_code"],

        "logs":
            job["logs"],

        "output":
            job["output"]

    }

    return jsonify(response)


# ==================================================
# Start Application
# ==================================================

if __name__ == "__main__":

    socketio.run(

        app,

        host="0.0.0.0",

        port=5000,

        debug=True

    )