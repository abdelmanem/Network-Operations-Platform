# Collector Runtime Framework

The collector runtime framework executes reusable collector jobs without
embedding vendor-specific command logic.

## Flow

1. Accept a discovery target and runtime constraints.
2. Resolve a collector from the registry.
3. Resolve a compatible transport from the transport manager.
4. Execute the collector against the target.
5. Parse the raw output into structured records.
6. Normalize the parsed output into canonical snapshot entities.
7. Persist the immutable snapshot through the snapshot repository.

## Components

- `backend/app/collectors/runtime/context.py` defines runtime inputs.
- `backend/app/collectors/runtime/job.py` defines queued job primitives.
- `backend/app/collectors/runtime/state.py` tracks execution state.
- `backend/app/collectors/runtime/scheduler.py` queues jobs.
- `backend/app/collectors/runtime/dispatcher.py` dispatches jobs.
- `backend/app/collectors/runtime/executor.py` executes the end-to-end flow.
- `backend/app/collectors/runtime/engine.py` coordinates runtime services.
- `backend/app/collectors/runtime/metrics.py` tracks runtime metrics.
- `backend/app/collectors/runtime/lifecycle.py` manages startup and shutdown.

## Design Notes

- Execution is async-friendly and framework-agnostic.
- Cancellation, retry, and timeout handling are built into the runtime layer.
- The runtime stores no business logic and no vendor-specific behavior.
- Collector and transport selection are driven by capability metadata.

