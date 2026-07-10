.PHONY: dev test lint eval eval-baseline eval-check frontend

dev:            ## Run the API locally with reload
	python -m uvicorn app.main:app --reload

test:           ## Run the backend test suite (hermetic, no API keys needed)
	python -m pytest -q

lint:           ## Ruff lint + format check
	ruff check app tests evals

eval:           ## Run the full eval suite (needs GROQ_API_KEY + TAVILY_API_KEY)
	python -m evals.run_evals

eval-baseline:  ## Run evals and promote the results to baseline
	python -m evals.run_evals --save-baseline

eval-check:     ## Run evals and fail on >10% regression vs baseline
	python -m evals.run_evals --compare

frontend:       ## Run the Next.js frontend dev server
	cd frontend && npm run dev
