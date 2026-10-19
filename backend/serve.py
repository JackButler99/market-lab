"""One production process: Waitress threads + two schedulers + persistent SQLite."""

import signal

import automation
import cross_fundamentals
import deploy_config
import fundamentals
import process_lock
import server
from wsgi_app import application


def main():
    from waitress.server import create_server

    host, port = deploy_config.validate()
    with process_lock.exclusive(str(server.DB) + ".process.lock"):
        http = create_server(
            application,
            host=host,
            port=port,
            threads=8,
            max_request_body_size=2_000_000,
            channel_timeout=180,
            expose_tracebacks=False,
        )
        try:
            server.init()
            server.AUTOMATION = automation.Runner(
                server.conn, server.sync_market, server.experiment, server.save_experiment
            )
            server.FUNDAMENTALS_AUTOMATION = fundamentals.Runner(
                server.conn,
                symbols=["AAPL", "MSFT", "EURUSD", "BTCUSD"],
                credential=cross_fundamentals.credential,
            )
            server.AUTOMATION.start()
            server.FUNDAMENTALS_AUTOMATION.start()

            def terminate(signum, frame):
                raise KeyboardInterrupt

            signal.signal(signal.SIGTERM, terminate)
            print("Production API ready; one database owner and scheduler process", flush=True)
            http.run()
        except KeyboardInterrupt:
            pass
        finally:
            for worker in (server.AUTOMATION, server.FUNDAMENTALS_AUTOMATION):
                if worker:
                    worker.stop_event.set()
            for worker in (server.AUTOMATION, server.FUNDAMENTALS_AUTOMATION):
                if worker:
                    worker.stop()
            http.close()


if __name__ == "__main__":
    main()
