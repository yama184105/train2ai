@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>train2ai</title>
        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                font-family: Inter, Arial, sans-serif;
                background: linear-gradient(180deg, #f7f8fb 0%, #eef2ff 100%);
                color: #111827;
            }

            .container {
                max-width: 1100px;
                margin: 0 auto;
                padding: 48px 20px 80px;
            }

            .hero {
                display: grid;
                grid-template-columns: 1.1fr 0.9fr;
                gap: 32px;
                align-items: center;
                min-height: 80vh;
            }

            .badge {
                display: inline-block;
                padding: 8px 12px;
                border-radius: 999px;
                background: #e0e7ff;
                color: #3730a3;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 18px;
            }

            h1 {
                font-size: 56px;
                line-height: 1.05;
                margin: 0 0 16px;
                letter-spacing: -1.5px;
            }

            .lead {
                font-size: 20px;
                line-height: 1.7;
                color: #4b5563;
                max-width: 620px;
                margin-bottom: 28px;
            }

            .bullets {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 28px;
            }

            .chip {
                padding: 10px 14px;
                border-radius: 999px;
                background: white;
                border: 1px solid #e5e7eb;
                font-size: 14px;
                color: #374151;
            }

            .card {
                background: rgba(255, 255, 255, 0.88);
                backdrop-filter: blur(10px);
                border: 1px solid #e5e7eb;
                border-radius: 24px;
                padding: 28px;
                box-shadow: 0 20px 60px rgba(17, 24, 39, 0.08);
            }

            .card h2 {
                margin: 0 0 8px;
                font-size: 24px;
            }

            .card p {
                margin: 0 0 18px;
                color: #6b7280;
                font-size: 14px;
                line-height: 1.6;
            }

            label {
                display: block;
                font-size: 14px;
                font-weight: 600;
                margin: 16px 0 8px;
                color: #374151;
            }

            input[type="file"],
            input[type="date"],
            select,
            button {
                width: 100%;
                border-radius: 12px;
                border: 1px solid #d1d5db;
                padding: 12px 14px;
                font-size: 15px;
                background: white;
            }

            input[type="file"] {
                padding: 10px;
            }

            .row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }

            button {
                margin-top: 22px;
                background: #111827;
                color: white;
                border: none;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.08s ease, opacity 0.2s ease;
            }

            button:hover {
                opacity: 0.95;
            }

            button:active {
                transform: translateY(1px);
            }

            .plan-box {
                margin-top: 18px;
                padding: 14px 16px;
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                font-size: 14px;
                color: #4b5563;
                line-height: 1.7;
            }

            .foot {
                margin-top: 14px;
                font-size: 12px;
                color: #9ca3af;
            }

            .preview {
                margin-top: 28px;
                background: #111827;
                color: #e5e7eb;
                border-radius: 20px;
                padding: 20px;
                font-size: 13px;
                line-height: 1.65;
                overflow: auto;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            }

            .preview .dim {
                color: #9ca3af;
            }

            @media (max-width: 900px) {
                .hero {
                    grid-template-columns: 1fr;
                    min-height: auto;
                }

                h1 {
                    font-size: 42px;
                }
            }

            @media (max-width: 640px) {
                .row {
                    grid-template-columns: 1fr;
                }

                .container {
                    padding-top: 28px;
                }

                h1 {
                    font-size: 36px;
                }

                .lead {
                    font-size: 17px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <section class="hero">
                <div>
                    <div class="badge">Garmin → AI-ready JSON</div>
                    <h1>Turn training data into something AI can actually use.</h1>
                    <p class="lead">
                        Upload your Garmin export ZIP and get clean JSON for ChatGPT, Claude, and Gemini.
                        No analysis inside the app. Just structured data, ready for your AI workflow.
                    </p>

                    <div class="bullets">
                        <div class="chip">Daily summary</div>
                        <div class="chip">Sleep</div>
                        <div class="chip">Workouts</div>
                        <div class="chip">Free: 7 days</div>
                        <div class="chip">3 exports / month</div>
                    </div>

                    <div class="preview">
<pre style="margin:0; white-space:pre-wrap;">{
  <span class="dim">"source"</span>: "garmin",
  <span class="dim">"date_range"</span>: { "start": "2026-03-01", "end": "2026-03-07" },
  <span class="dim">"daily_summary"</span>: [...],
  <span class="dim">"sleep"</span>: [...],
  <span class="dim">"workouts"</span>: [...]
}</pre>
                    </div>
                </div>

                <div class="card">
                    <h2>Generate dataset</h2>
                    <p>
                        Export your Garmin data, choose a date range, and download a clean dataset JSON.
                    </p>

                    <form action="/upload" method="post" enctype="multipart/form-data">
                        <label for="file">Garmin export ZIP</label>
                        <input type="file" id="file" name="file" accept=".zip" required />

                        <div class="row">
                            <div>
                                <label for="start_date">Start date</label>
                                <input type="date" id="start_date" name="start_date" required />
                            </div>
                            <div>
                                <label for="end_date">End date</label>
                                <input type="date" id="end_date" name="end_date" required />
                            </div>
                        </div>

                        <label for="plan">Plan</label>
                        <select id="plan" name="plan" required>
                            <option value="free" selected>Free</option>
                            <option value="pro">Pro</option>
                        </select>

                        <button type="submit">Generate dataset</button>
                    </form>

                    <div class="plan-box">
                        <strong>Free</strong>: up to 7 days per export, 3 exports per month.<br>
                        <strong>Pro</strong>: up to 365 days per export.
                    </div>

                    <div class="foot">
                        Supported today: Garmin. Strava coming later.
                    </div>
                </div>
            </section>
        </div>
    </body>
    </html>
    """
