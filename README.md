<p align="center">
  
  <img src="https://github.com/usestrix/.github/raw/main/imgs/cover.png" alt="Strix Banner" width="100%">
  
</p>

<div align="center">

# Strix

### The open-source AI pentesting tool. Autonomous AI hackers that find and fix your app’s vulnerabilities.

<br/>

</div>


> [!TIP]
> Strix integrates seamlessly with GitHub Actions and CI/CD pipelines. Automatically scan for vulnerabilities on every pull request and block insecure code before it reaches production - see [CI/CD (GitHub Actions)](#cicd-github-actions) below, or run the full dashboard yourself with [`saas/dev.sh`](#-developer-environment-setup) for scheduled/managed scanning.

---


## Strix Overview

Strix are autonomous AI penetration testing agents that act just like real hackers - they run your code dynamically, find vulnerabilities, and validate them through actual proofs-of-concept. Built for developers and security teams who need fast, accurate security testing without the overhead of manual pentesting or the false positives of static analysis tools.

**Key Capabilities:**

- **Full pentesting toolkit** - reconnaissance, exploitation, and validation out of the box
- **Multi-agent orchestration** - teams of AI pentesters that collaborate and scale
- **Real exploit validation** - working PoCs, not false positives like legacy vulnerability scanners
- **Developer‑first CLI** - actionable findings with remediation guidance
- **Auto‑fix & reporting** - generate patches and compliance-ready pentest reports


<br>


<div align="center">
  <img src=".github/screenshot.png" alt="Strix Demo" width="1000" style="border-radius: 16px;">
</div>


## Use Cases

- **Application Security Testing** - Detect and validate critical vulnerabilities in your applications
- **Rapid Penetration Testing** - Get penetration tests done in hours, not weeks, with compliance reports
- **Bug Bounty Automation** - Automate bug bounty research and generate PoCs for faster reporting
- **CI/CD Integration** - Run tests in CI/CD to block vulnerabilities before reaching production

## 🚀 Quick Start

**Prerequisites:**
- Docker (running)
- An LLM API key from any [supported provider](docs/llm-providers/overview.mdx) (OpenAI, Anthropic, Google, etc.)

### Installation & First Scan

```bash
# Install Strix (this fork, not the upstream package)
pip install "strix-agent @ git+https://github.com/maruthis/strix"

# Configure your AI provider
export STRIX_LLM="openai/gpt-5.4"
export LLM_API_KEY="your-api-key"

# Run your first security assessment
strix --target ./app-directory
```

> [!NOTE]
> First run automatically pulls the sandbox Docker image. Results are saved to `strix_runs/<run-name>`

### Or: run the full SaaS dashboard

Want the multi-tenant dashboard (org accounts, connected repos/domains,
scheduled scans, PR reviews, Chat) instead of the bare CLI? One command
brings up both the backend and frontend together:

```bash
saas/dev.sh
```

This installs backend (`uv sync`) and frontend (`npm install`) dependencies
on first run, then starts the API on `:8000` and the dashboard on `:5173`
— `Ctrl-C` stops both. It runs against the mock scanner by default (no
Docker/LLM key needed to explore the UI); set `SAAS_ENABLE_REAL_SCAN=1` in
`saas/backend/.env` once you want it to run genuine scans through this
same engine. See [Developer Environment Setup](#-developer-environment-setup)
below for the full picture, or [`saas/README.md`](saas/README.md) directly.

---

## ☁️ Strix Platform

This repo includes the full-stack penetration testing platform's source under
[`saas/`](saas/) — a multi-tenant dashboard you self-host rather than a
service this fork operates. Deploy it wherever you like (e.g.
`<servername>.strix.ai`, or any domain/subdomain you control), sign in,
connect your repos and domains, and launch a pentest in minutes.

- **Validated findings with PoCs** - every vulnerability includes a working proof-of-concept exploit and reproduction steps
- **One-click autofix** - AI-generated security patches as ready-to-merge pull requests
- **Continuous pentesting** - always-on vulnerability scanning that keeps pace with your deployments
- **DevSecOps integrations** - GitHub, GitLab, Bitbucket, Slack, Jira, Linear, and CI/CD pipelines
- **Continuous learning** - AI that builds on past findings, adapts to your codebase, and reduces false positives over time

**[Run it locally with `saas/dev.sh` →](#-developer-environment-setup)** or see [`saas/README.md`](saas/README.md) for deploying your own instance.

---

## 🤖 Use Strix from Your Coding Agent

Strix is agent-ready. Give Claude Code, Cursor, Codex, or any [SKILL.md-compatible](https://agentskills.io) agent the ability to run pentests, fix findings, and set up CI scanning:

```bash
npx skills add maruthis/strix
```

This installs three skills: **penetration-testing-with-strix** (run headless scans and read results), **fix-security-vulnerabilities-with-strix** (remediate + re-scan to verify), and **ci-security-scanning-with-strix** (PR scanning in CI). All three install and run this fork (`pip install "strix-agent @ git+https://github.com/maruthis/strix"`), not the upstream package, so agents get this fork's changes — see [`docs/extending-without-code-changes.md`](docs/extending-without-code-changes.md). Read [`AGENTS.md`](AGENTS.md) for a quick reference.

---

## ✨ Features

### Agentic Pentesting Tools

Strix agents come equipped with a comprehensive offensive security toolkit - the same tools used by professional penetration testers and ethical hackers:

- **HTTP Interception Proxy** - Full request/response manipulation and analysis with Caido
- **Browser Exploitation** - Automated browser for testing XSS, CSRF, clickjacking, and auth bypass flows
- **Shell & Command Execution** - Interactive terminal for exploit development and post-exploitation
- **Custom Exploit Runtime** - Python sandbox for writing and validating proof-of-concept exploits
- **Reconnaissance & OSINT** - Automated attack surface mapping, subdomain enumeration, and fingerprinting
- **Static & Dynamic Code Analysis** - SAST + DAST capabilities for comprehensive application security testing
- **Vulnerability Knowledge Base** - Structured findings with CVSS scoring and OWASP classification

### Comprehensive Vulnerability Scanner

Strix identifies, validates, and exploits a wide range of security vulnerabilities across the OWASP Top 10 and beyond:

- **Broken Access Control** - IDOR, privilege escalation, auth bypass
- **Injection Attacks** - SQL injection, NoSQL injection, OS command injection, SSTI
- **Server-Side Vulnerabilities** - SSRF, XXE, insecure deserialization, RCE
- **Client-Side Attacks** - XSS (stored/reflected/DOM), prototype pollution, CSRF
- **Business Logic Flaws** - Race conditions, payment manipulation, workflow bypass
- **Authentication & Session** - JWT attacks, session fixation, credential stuffing vectors
- **Infrastructure & Cloud** - Misconfigurations, exposed services, cloud security issues
- **API Security** - Broken authentication, mass assignment, rate limiting bypass

### Graph of Agents (Multi-Agent Pentesting)

Advanced multi-agent orchestration for comprehensive automated penetration testing:

- **Distributed Pentesting** - Specialized AI agents for recon, exploitation, and post-exploitation
- **Scalable Security Testing** - Parallel execution across multiple targets for fast, comprehensive coverage
- **Dynamic Coordination** - Agents share discoveries, chain vulnerabilities, and collaborate like a red team

---

## 🖥️ Local Web Viewer

Every scan writes its results to disk as it runs. Bring them up in a local dashboard with a single command:

```bash
# Open the most recent run
strix view

# ...or open a specific run by name
strix view my-run-name
```

`strix view` starts a lightweight local server (bound to `127.0.0.1` on a random port) and opens your browser to a private, tokened link. Nothing leaves your machine: the dashboard reads the run's files straight off disk, with no cloud account or upload required. The UI ships prebuilt with Strix, so there is no extra install and no JS build step.

### What's in the dashboard

- **Overview**: run status, target, and a severity breakdown of everything found so far.
- **Vulnerabilities**: each validated finding with its severity, details, and reproduction steps.
- **Agent graph**: a live map of the multi-agent team, showing which agent is doing what.
- **Steering**: send instructions to a live scan from the browser to redirect the agents mid-run.
- **History**: browse past runs on this machine and jump between them.
- **Reports**: generate a shareable report and email it to yourself or your team.

---

## Usage Examples

### Basic Usage

```bash
# Scan a local codebase
strix --target ./app-directory

# Security review of a GitHub repository
strix --target https://github.com/org/repo

# Black-box web application assessment
strix --target https://your-app.com
```

### API Testing (OpenAPI / Swagger / Postman)

Point Strix at an API contract and it tests every declared endpoint instead of
having to discover them by crawling. Pair the spec with the live base URL so the
agent knows where to send traffic:

```bash
# OpenAPI / Swagger file (.json / .yaml)
strix --target ./openapi.yaml --target https://api.your-app.com

# Postman collection export
strix --target ./collection.postman_collection.json --target https://api.your-app.com

# Postman collection pulled live by id (no manual export)
export POSTMAN_API_KEY="PMAK-..."
strix --target postman://<collection-uuid>

# ...with a Postman environment to resolve {{baseUrl}} / token variables
strix --target "postman://<collection-uuid>?env=<environment-uuid>"
```


### Advanced Testing Scenarios

```bash
# Grey-box authenticated testing
strix --target https://your-app.com --instruction "Perform authenticated testing using credentials: user:pass"

# Multi-target testing (source code + deployed app)
strix -t https://github.com/org/app -t https://your-app.com

# Targets from a file, one target per non-empty, non-comment line
strix --target-list ./targets.txt

# White-box source-aware scan (local repository)
strix --target ./app-directory --scan-mode standard

# Focused testing with custom instructions
strix --target api.your-app.com --instruction "Focus on business logic flaws and IDOR vulnerabilities"

# Provide detailed instructions through file (e.g., rules of engagement, scope, exclusions)
strix --target api.your-app.com --instruction-file ./instruction.md

# Force PR diff-scope against a specific base branch
strix -n --target ./ --scan-mode quick --scope-mode diff --diff-base origin/main
```

### Headless Mode

Run Strix programmatically without interactive UI using the `-n/--non-interactive` flag - perfect for servers and automated jobs. The CLI prints real-time vulnerability findings and the final report before exiting. Exits with non-zero code when vulnerabilities are found.

```bash
strix -n --target https://your-app.com
```

### CI/CD (GitHub Actions)

Strix can be added to your pipeline to run a security test on pull requests with a lightweight GitHub Actions workflow:

```yaml
name: strix-penetration-test

on:
  pull_request:

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install Strix
        run: pip install "strix-agent @ git+https://github.com/maruthis/strix"

      - name: Run Strix
        env:
          STRIX_LLM: ${{ secrets.STRIX_LLM }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}

        run: strix -n -t ./ --scan-mode quick
```

> [!TIP]
> In CI pull request runs, Strix automatically scopes quick reviews to changed files.
> If diff-scope cannot resolve, ensure checkout uses full history (`fetch-depth: 0`) or pass
> `--diff-base` explicitly.

### Configuration

```bash
export STRIX_LLM="openai/gpt-5.4"
export LLM_API_KEY="your-api-key"

# Optional
export LLM_API_BASE="your-api-base-url"  # if using a local model, e.g. Ollama, LMStudio
export PERPLEXITY_API_KEY="your-api-key"  # for search capabilities
export STRIX_REASONING_EFFORT="high"  # control thinking effort (default: high, quick scan: medium)
```

> [!NOTE]
> Strix automatically saves your configuration to `~/.strix/cli-config.json`, so you don't have to re-enter it on every run.

#### Sign in with a ChatGPT subscription

Instead of a metered API key, you can run Strix on your ChatGPT Plus/Pro subscription:

```bash
strix auth login chatgpt      # sign in with your ChatGPT account

export STRIX_LLM="chatgpt/gpt-5.4"   # chatgpt/<model> runs on the subscription
strix --target ./app-directory

strix auth status             # show the active sign-in
strix auth logout             # forget the sign-in
```

**Recommended models for best results:**

- [OpenAI GPT-5.4](https://openai.com/api/) - `openai/gpt-5.4`
- [Anthropic Claude Sonnet 4.6](https://claude.com/platform/api) - `anthropic/claude-sonnet-4-6`
- [Google Gemini 3 Pro Preview](https://cloud.google.com/vertex-ai) - `vertex_ai/gemini-3-pro-preview`

See the [LLM Providers documentation](docs/llm-providers/overview.mdx) for all supported providers including Vertex AI, Bedrock, Azure, and local models.

## Enterprise Pentesting

`saas/` is already built for this: multi-tenant orgs with role-based
access, custom compliance-ready penetration testing reports, GitHub/GitLab
integrations, BYOK model support (per-org LLM settings), and self-hosted
deployment by construction (there's no hosted version to opt out of). See
[`docs/saas-architecture.md`](docs/saas-architecture.md) for how it's put
together, and [`saas/README.md`](saas/README.md) to deploy your own
instance (e.g. at `<servername>.strix.ai`) with SSO/VPC controls layered
on however your infrastructure normally handles that.

## Documentation

Full documentation is available under [`docs/`](docs/) in this repository
— including detailed guides for usage, CI/CD integrations, skills, and
advanced configuration. Start at [`docs/README.md`](docs/README.md) or
[`docs/quickstart.mdx`](docs/quickstart.mdx).

## 🛠️ Developer Environment Setup

Two things live in this repo — the `strix` engine (Python CLI/library) and
`saas/` (the multi-tenant dashboard built on top of it) — each with its
own setup.

### Engine (`strix/`)

```bash
git clone https://github.com/maruthis/strix.git
cd strix

make dev-install     # uv sync + dev dependencies
make check-all        # ruff format/lint, mypy, pyright, bandit
uv run pytest          # run the test suite
uv run strix --target ./some-project   # run from source
```

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/). `make
setup-dev` also installs the pre-commit hooks. See
[`AGENTS.md`](AGENTS.md)'s "Contributing to this repo" section and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide, and
[`docs/strix-engine-architecture.md`](docs/strix-engine-architecture.md)
for how the engine itself is structured.

### SaaS dashboard (`saas/`)

The fastest way to get the backend and frontend running together:

```bash
saas/dev.sh
```

What it does (see the script's own header comment for the full detail):

- Installs backend deps (`uv sync`, in `saas/backend/`) and frontend deps
  (`npm install`, in `saas/frontend/`) on first run.
- Starts the FastAPI backend on `:8000` and the Vite dev server on
  `:5173`, and stops both together on `Ctrl-C`.
- Auto-loads `saas/backend/.env` (gitignored — copy it from
  `saas/backend/.env.example`) before doing anything else, so you don't
  have to re-export environment variables every run.
- Runs against the built-in mock scanner by default — no Docker or LLM
  key needed just to explore the UI. Set `SAAS_ENABLE_REAL_SCAN=1` in
  that `.env` file (and a Docker + `STRIX_LLM`/`LLM_API_KEY` setup, same
  as the engine above) to run genuine scans through this same engine
  instead of canned findings.

Requires `uv` and `npm`/Node.js. Prerequisites, environment variables,
manual (non-`dev.sh`) startup, and the backend test suite are all covered
in [`saas/README.md`](saas/README.md) and [`saas/CONFIG.md`](saas/CONFIG.md);
[`docs/saas-architecture.md`](docs/saas-architecture.md) covers how the
backend, frontend, and data model fit together.

## Contributing

We welcome contributions of code, docs, and new skills - check out our [Contributing Guide](docs/contributing.mdx) to get started or open a [pull request](https://github.com/maruthis/strix/pulls)/[issue](https://github.com/maruthis/strix/issues).

## Join Our Community

Have questions? Found a bug? Want to contribute? **[Join our Discord!](https://discord.gg/strix-ai)**

## Support the Project

**Love Strix?** Give us a ⭐ on GitHub!

## Acknowledgements

Strix builds on the incredible work of open-source projects like [LiteLLM](https://github.com/BerriAI/litellm), [Caido](https://github.com/caido/caido), [Nuclei](https://github.com/projectdiscovery/nuclei), [Playwright](https://github.com/microsoft/playwright), and [Bubble Tea](https://github.com/charmbracelet/bubbletea). Huge thanks to their maintainers!


> [!WARNING]
> **Authorized use only.** Strix actively tests the targets you point it at, so only run it against systems you own or have **explicit, written permission** to test, and stay within the agreed scope. Unauthorized testing is illegal in most jurisdictions.
> You alone are responsible for obtaining authorization and complying with the law. Strix is provided "as is" with no warranty or liability for misuse.

</div>
