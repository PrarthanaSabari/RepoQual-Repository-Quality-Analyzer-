# RepoQual-Repository-Quality-Analyzer

A Flask-based web application that analyzes a public GitHub repository and checks whether it is **research-software-ready**.

The tool lets a user paste a GitHub repository URL into a webpage, then evaluates the repository using a weighted scoring system and generates:
- A score out of 100
- A short rationale for each check
- A prioritized fix checklist
- A downloadable JSON report
- A downloadable HTML report

## Features

This project checks the following repository quality indicators:

- README quality, including whether installation/setup and usage/run instructions are present
- License file presence
- Test file/folder presence
- Test command detection
- CI configuration presence, such as GitHub Actions or GitLab CI
- Versioning/release history using releases or tags
- Citation support using `CITATION.cff` or README citation/reference sections

## Scoring

The project uses a weighted score out of 100.

| Check | Weight |
|---|---:|
| README Quality | 20 |
| License | 15 |
| Tests Present | 15 |
| Test Command | 20 |
| CI Configuration | 10 |
| Versioning/Releases | 10 |
| Citation Support | 10 |

## Tech Stack

- Python
- Flask
- Requests
- HTML, CSS, JavaScript
- GitHub REST API

## Project Structure

```text
repo-ready-webapp/
│
├── app.py
├── output/
└── templates/
    └── index.html
```

## Prerequisites

Before running this project, make sure you have:

- Python 3.9 or above installed
- `pip` installed
- Internet connection to access GitHub API

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

2. Install dependencies:

```bash
pip install flask requests
```

## How to Run

Run the Flask app using:

```bash
python app.py
```

After starting the server, open this URL in your browser:

```text
http://127.0.0.1:5000
```

## How to Use

1. Open the webpage in your browser.
2. Paste a public GitHub repository URL.
3. Click **Analyze Repo**.
4. View the repository score and detailed check results.
5. Download the generated JSON and HTML reports from the webpage.

## Example Input

```text
https://github.com/pallets/flask
```

## Output

The application generates:

- A score out of 100
- Per-check pass/partial/fail status
- Short rationale for each check
- A prioritized fix checklist
- Downloadable report files saved in the `output/` folder

## Current Limitation

In the current version, the app detects likely test files and infers a test command, but it does not fully clone and execute repository tests in an isolated environment. This version is mainly intended as an MVP for repository quality assessment through GitHub metadata and file inspection.

## Future Improvements

Possible extensions include:

- Clone repositories and execute test commands safely
- Support private repositories using GitHub tokens
- Add branch-aware analysis
- Improve README quality scoring using section parsing
- Add support for more ecosystems such as Maven, Gradle, and R packages
- Add charts or historical comparison across multiple repositories

## License

This project currently does not include a license by default.  
You should add an appropriate open-source license such as MIT if you plan to publish it publicly.

## Author

Developed as an academic/project submission for automated assessment of research software readiness.
