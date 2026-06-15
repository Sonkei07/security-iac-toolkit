.PHONY: install scan-secrets drift cost tagging opa-test lint

install:
	pip install -r requirements.txt

scan-secrets:
	python scanner/secret_scanner.py --path $(PATH)

drift:
	python drift/drift_detector.py --state $(STATE) --region $(REGION)

cost:
	python cost/cost_estimator.py --plan $(PLAN)

tagging:
	python tagging/tag_enforcer.py --path $(PATH)

opa-test:
	opa test opa/policies/ opa/tests/ -v

lint:
	pip install ruff --quiet && ruff check .
