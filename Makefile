PYTHON ?= python
CXX ?= g++
CXXFLAGS = -std=c++17 -Wall -Wextra -Werror -Wpedantic
CC ?= cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -Wpedantic
.PHONY: simulate test board-live-sim board-media-sync-sim combined-acquisition-sim live-host-sim embedded sanitize hardware-stress electrical-sim
simulate:
	$(PYTHON) run_simulation.py --seeds 10
test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
board-live-sim:
	$(PYTHON) scripts/board_live_sim.py --output results/board_live_simulation.json
board-media-sync-sim:
	$(PYTHON) scripts/board_media_sync_sim.py --output results/board_media_sync_simulation.json
combined-acquisition-sim:
	$(PYTHON) scripts/combined_acquisition_sim.py --output results/combined_acquisition_simulation.json
live-host-sim:
	$(PYTHON) scripts/live_host_runtime_sim.py --output results/live_host_runtime_simulation.json
embedded:
	$(CXX) $(CXXFLAGS) tests/embedded_test.cpp -o embedded-tests
	./embedded-tests
sanitize:
	$(CXX) $(CXXFLAGS) -fsanitize=address,undefined -fno-omit-frame-pointer -g tests/embedded_test.cpp -o embedded-tests-sanitized
	./embedded-tests-sanitized
hardware-stress:
	$(CXX) $(CXXFLAGS) tests/hardware_stress.cpp -o hardware-stress
	./hardware-stress

electrical-sim:
	$(PYTHON) hardware/electrical_interface_sim.py > electrical-sim.json
	$(PYTHON) hardware/power_distribution_model.py > power-distribution-model.txt

.PHONY: incident-build c-sanitize incidents
incident-build:
	mkdir -p build
	$(CXX) $(CXXFLAGS) tests/board_stream.cpp -o build/board-stream
	$(CC) $(CFLAGS) -O2 -fPIC -shared csrc/detection.c -lm -o build/libdetection.so

c-sanitize:
	mkdir -p build
	$(CC) $(CFLAGS) -fsanitize=address,undefined -fno-omit-frame-pointer -g tests/c_core_test.c csrc/detection.c -lm -o build/c-core-test
	./build/c-core-test

incidents: incident-build
	$(PYTHON) run_incidents.py --c-library build/libdetection.so
