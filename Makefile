# SuperAI SS6 — one-command workflows. Everything here is $0 (local + mock provider).
SHELL := /bin/bash
REQ ?= Add a Top Customers by Spend analytics endpoint
DOCKER ?= docker

.PHONY: help install test eval pipeline demo up down clean

help:
	@echo "make install   # pip install -e . (adds the ss6 command)"
	@echo "make test      # run the Python unit tests (pytest)"
	@echo "make eval      # run the four phase eval harnesses"
	@echo "make pipeline  # ss6 run on a sample requirement (offline, mock)"
	@echo "make demo      # closed loop: generate -> real tsc+jest gate -> apply -> rebuild API -> curl -> draft PR"
	@echo "make up / down # start / stop the eleven-7 Docker stack"

install:
	pip install -e .

test:
	SS6_LLM_PROVIDER=mock python -m pytest -q

eval:
	SS6_LLM_PROVIDER=mock python eval/plan_quality.py --plans out/plans.json || true
	SS6_LLM_PROVIDER=mock python eval/debate_quality.py --plans out/plans.json || true
	SS6_LLM_PROVIDER=mock python eval/design_quality.py --design out/plans.json || true
	SS6_LLM_PROVIDER=mock python eval/execution_quality.py || true

pipeline:
	SS6_LLM_PROVIDER=mock ss6 run "$(REQ)" --out ./out

demo:
	bash scripts/ss6_demo.sh "$(REQ)"

up:
	cd target_repo && $(DOCKER) compose up -d --build

down:
	cd target_repo && $(DOCKER) compose down -v

clean:
	rm -rf out/exec .chroma **/__pycache__ *.egg-info
