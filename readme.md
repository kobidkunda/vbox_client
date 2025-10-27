# Vicidial Playback Application

This is a lightweight, high-performance FastAPI application designed to run on a Vicidial server. Its sole purpose is to serve pre-generated audio files and API responses to the local Vicidial instance with minimal latency.

This application **does not** perform any audio generation, AI rephrasing, or heavy processing. It is a "read-only" playback and preview environment.

## Core Technologies

*   **Backend:** FastAPI
*   **Web Server:** Gunicorn with Uvicorn workers
*   **Database:** PostgreSQL (local instance)
*   **Service Management:** systemd

---

## The "Campaign-in-a-Box" Workflow

This application works on an export/import model. The workflow is as follows:

1.  **Generate & Export:** On a separate, powerful GPU server, a campaign is created, and all audio files are generated. The campaign (leads data + audio files) is then exported as a single `.zip` package.
2.  **Import & Deploy:** The `.zip` package is uploaded to this Playback Application via its web interface. The import process completely wipes all old data and deploys the new campaign, populating the local database and copying the audio files.
3.  **Preview:** The application's dashboard can be used to preview the imported leads and listen to the audio files to ensure everything is correct before dialing.
4.  **Serve:** The Vicidial dialer makes API calls to `http://localhost:8001`, which are answered instantly by this local application.

---

## Day-to-Day Management

All management is done via the command line on the Vicidial server.

### Managing the Service (`systemctl`)

The application runs as a `systemd` service, which means it starts on boot and restarts if it fails.

*   **Check the status of the application:**
    ```bash
    sudo systemctl status playback_app.service
    ```
    *(Look for a green `active (running)` message).*

*   **Stop the application:**
    ```bash
    sudo systemctl stop playback_app.service
    ```

*   **Start the application:**
    ```bash
    sudo systemctl start playback_app.service
    ```

*   **Restart the application (after making code changes):**
    ```bash
    sudo systemctl restart playback_app.service
    ```

### Viewing Logs (`journalctl`)

All output from the application (including errors) is captured by `journalctl`. This is the most important tool for debugging.

*   **View the latest logs and follow in real-time:**
    ```bash
    sudo journalctl -u playback_app.service -n 100 -f
    ```
    *   `-u playback_app.service`: Shows logs for our app only.
    *   `-n 100`: Shows the last 100 lines.
    *   `-f`: "Follows" the log file to show new messages as they happen.

---

## Deploying a New Campaign

1.  Obtain the `Campaign-Package.zip` file from the GPU server.
2.  Open a web browser and navigate to the importer page: `http://<YOUR_VICIDIAL_IP>:8001/importer`.
3.  Upload the `.zip` file and click "Upload and Deploy."
4.  Watch the logs (`journalctl -u playback_app.service -f`) to see the import progress.
5.  Once complete, navigate to the dashboard `http://<YOUR_VICIDIAL_IP>:8001/dashboard` to verify the data.

---

## Configuration

The application is configured via the `.env` file in the root directory (`/srv/playback_app/.env`).

*   `DATABASE_URL`: The connection string for the **local** PostgreSQL database.
*   `AUDIO_STORAGE_PATH`: The absolute path on this server where audio files are stored.
*   `BASE_URL`: The URL of this server, used for constructing audio file URLs in API responses.

---

## Troubleshooting

*   **Problem:** The service fails to start with `status=217/USER`.
    *   **Solution:** The `User=` or `Group=` in `/etc/systemd/system/playback_app.service` is incorrect. Find the correct owner of the `/srv/playback_app` directory with `ls -ld /srv/playback_app` and update the service file, then run `sudo systemctl daemon-reload`.

*   **Problem:** The dashboard is empty after a "successful" import message.
    *   **Solution:** This means the database import failed silently. This is usually due to a format mismatch in the CSV or SQL file. Check the logs with `journalctl` while re-uploading the package. The detailed error message will be visible there.

*   **Problem:** Cannot access the web interface from a browser.
    *   **Solution:** This is a firewall issue. Ensure the external firewall (from your hosting provider) allows incoming TCP traffic on the port specified in the service file (e.g., 8001).