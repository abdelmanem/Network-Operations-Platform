import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from backend.app.models.base import BaseModel
from backend.app.jobs import InMemoryJobRepository, JobManager, JobRequest
from backend.app.orchestration import WorkflowEngine, OrchestrationEngine, OrchestrationContext, CancellationToken
from backend.app.orchestration.coordinator import DiscoveryCoordinator
from backend.app.comparison.engine import ComparisonEngine
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.discovery.context import DiscoveryTarget
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot as LiveInventorySnapshot
from backend.app.inventory.entities import Device, DeviceType, Manufacturer
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.compliance.domain.enums import RuleStatus

class FakeInventoryService:
    def __init__(self, snapshot, fail_once=False):
        self.snapshot = snapshot
        self.fail_once = fail_once
        self.calls = 0

    async def synchronize(self, *, force_refresh=False):
        self.calls += 1
        print('FakeInventoryService.synchronize call', self.calls)
        if self.fail_once and self.calls == 1:
            raise RuntimeError('temporary netbox failure')
        return self.snapshot

class FakeCollectorRuntime:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def collect(self, contexts):
        print('FakeCollectorRuntime.collect called')
        return self.snapshot, ()


def _netbox_snapshot():
    manufacturer = Manufacturer(name='Cisco', slug='cisco')
    device_type = DeviceType(manufacturer=manufacturer, model='WS-C2960X', slug='ws-c2960x')
    return NetBoxInventorySnapshot(devices=(Device(name='switch-01', device_type=device_type, serial='ABC123'),))


def _live_snapshot():
    return LiveInventorySnapshot(devices=(DeviceSnapshot(device_id='switch-01', name='switch-01', model='WS-C2960X', serial_number='XYZ999'),))


def _policy():
    rule = Rule.create(
        'serial-match',
        'Serial must match',
        RuleMetadata(version='1.0', status=RuleStatus.ACTIVE),
        expected_state={
            'rule_type': 'equals',
            'subject_type': 'device',
            'field_name': 'serial',
            'risk_score': 80,
        },
    )
    return Policy.create('Inventory Policy', rules=(rule,))


def _context(max_attempts=2, cancellation_token=None):
    return OrchestrationContext(
        collector_contexts=(
            CollectorRuntimeContext(
                target=DiscoveryTarget(identifier='switch-01', address='10.0.0.1')
            ),
        ),
        policies=(_policy(),),
        metadata={'site': 'HQ', 'device_role': 'access', 'platform': 'iosxe'},
        max_attempts=max_attempts,
        retry_delay_seconds=0.0,
        force_netbox_refresh=False,
        cancellation_token=cancellation_token or CancellationToken(),
    )


async def main() -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory() as db_session:
        workflow = WorkflowEngine(
            inventory_service=FakeInventoryService(_netbox_snapshot(), fail_once=True),
            discovery_coordinator=DiscoveryCoordinator(FakeCollectorRuntime(_live_snapshot())),
            comparison_engine=ComparisonEngine(),
            evaluation_engine=EvaluationEngine(),
            unit_of_work_factory=lambda: PersistenceUnitOfWork(db_session),
        )
        manager = JobManager(engine=OrchestrationEngine(workflow), repository=InMemoryJobRepository(), worker_count=1)
        await manager.start_workers()
        request = JobRequest(context=_context(max_attempts=2), timeout_seconds=5.0)
        submission = await manager.submit_job(request)
        print('submitted', submission.job.id, submission.job.state.status, submission.job.state.attempts)
        await asyncio.sleep(1.0)
        await manager.shutdown()
        job = await manager.get_job(submission.job.id)
        print('final', job.state.status, job.state.attempts)


if __name__ == '__main__':
    asyncio.run(main())
