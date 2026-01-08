.PHONY: format lint

format:
	$(MAKE) -C python format & $(MAKE) -C js format & wait

lint:
	$(MAKE) -C python lint & $(MAKE) -C js lint & wait
