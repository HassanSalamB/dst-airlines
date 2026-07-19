# DST Airlines DataOps

## Setup

1. **Clone the repo**
```bash
git clone git@github.com:kboroz/dst-airlines-DataOps.git
cd dst-airlines-DataOps/dst-airlines-DataOps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
docker compose up -d
