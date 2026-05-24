.PHONY: clean

all: server client
init: server-init client-init
complete: server-init client-init server client

server-init:
	python -m PyInstaller --onefile --name "test_server" test_server.py

server:
	python -m PyInstaller test_server.spec

client-init:
	python -m PyInstaller --onefile --name "gui_client" gui_client.py

client:
	python -m PyInstaller gui_client.spec

clean:
	rm -rf build
	rm -rf dist