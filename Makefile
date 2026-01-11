all: server client
init: server-init client-init

server-init:
	pyinstaller --onefile --name "test_server" test_server.py

server:
	pyinstaller test_server.spec

client-init:
	pyinstaller --onefile --name "test_client" test_client.py

client:
	pyinstaller test_client.spec

clean:
	rm -rf build
	rm -rf dist