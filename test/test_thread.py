import logging
import time

import pytest

from libb.thread import RateLimitedExecutor, TaskRequest

logger = logging.getLogger(__name__)


def test_rate_limiting_enforced():
    """Verify rate limiting prevents exceeding max_per_second threshold.
    """
    max_per_second = 5
    num_calls = 15

    call_times = []

    def record_call(i):
        call_times.append(time.time())
        return i

    with RateLimitedExecutor(max_workers=10, max_per_second=max_per_second) as executor:
        responses = executor.execute_items(record_call, list(range(num_calls)))

    assert len(responses) == num_calls
    assert all(r.success for r in responses)
    assert [r.result for r in responses] == list(range(num_calls))

    start_time = call_times[0]
    for i in range(len(call_times)):
        elapsed = call_times[i] - start_time
        calls_in_window = sum(1 for t in call_times[:i+1] if call_times[i] - t < 1.0)
        assert calls_in_window <= max_per_second, f'Rate limit violated at call {i}'

    total_duration = call_times[-1] - call_times[0]
    logger.debug(f'Completed {num_calls} calls in {total_duration:.2f}s with limit {max_per_second}/sec')


def test_parallel_execution():
    """Verify multiple tasks execute concurrently within rate limit.
    """
    def slow_task(duration):
        time.sleep(duration)
        return duration

    start = time.time()
    with RateLimitedExecutor(max_workers=5, max_per_second=10) as executor:
        responses = executor.execute_items(slow_task, [0.1] * 5)

    elapsed = time.time() - start

    assert len(responses) == 5
    assert all(r.success for r in responses)
    assert all(r.result == 0.1 for r in responses)
    assert elapsed < 0.5, f'Expected parallel execution, took {elapsed:.2f}s'
    logger.debug(f'5 parallel 0.1s tasks completed in {elapsed:.2f}s')


def test_no_rate_limit():
    """Verify executor works without rate limiting when max_per_second is inf.
    """
    num_calls = 20
    call_times = []

    def fast_call(i):
        call_times.append(time.time())
        return i

    start = time.time()
    with RateLimitedExecutor(max_workers=10) as executor:
        responses = executor.execute_items(fast_call, list(range(num_calls)))

    elapsed = time.time() - start

    assert len(responses) == num_calls
    assert all(r.success for r in responses)
    assert elapsed < 1.0, f'Unlimited executor should be fast, took {elapsed:.2f}s'
    logger.debug(f'{num_calls} unlimited calls completed in {elapsed:.2f}s')


def test_execute_items_basic():
    """Verify execute_items() processes all items and returns ordered results.
    """
    def process(x):
        return x * 2

    inputs = list(range(10))

    with RateLimitedExecutor(max_workers=5, max_per_second=20) as executor:
        responses = executor.execute_items(process, inputs)

    assert len(responses) == len(inputs)
    assert all(r.success for r in responses)
    assert [r.result for r in responses] == [x * 2 for x in inputs]
    assert [r.request.id for r in responses] == list(range(10))


def test_exception_handling():
    """Verify exceptions in submitted tasks are captured in responses.
    """
    def failing_task(x):
        if x == 5:
            raise ValueError(f'Task {x} failed')
        return x

    with RateLimitedExecutor(max_workers=5, max_per_second=10) as executor:
        responses = executor.execute_items(failing_task, list(range(10)))

    assert len(responses) == 10

    for i, response in enumerate(responses):
        if i == 5:
            assert not response.success
            assert isinstance(response.exception, ValueError)
            assert 'Task 5 failed' in str(response.exception)
        else:
            assert response.success
            assert response.result == i


def test_execute_preserves_order():
    """Verify execute() returns results in original request order despite completion order.
    """
    def task_with_delay(i):
        time.sleep(0.01 * (10 - i))
        return i

    with RateLimitedExecutor(max_workers=10, max_per_second=50) as executor:
        responses = executor.execute_items(task_with_delay, list(range(10)))

    assert len(responses) == 10
    assert all(r.success for r in responses)
    assert [r.result for r in responses] == list(range(10))
    assert [r.request.id for r in responses] == list(range(10))
    logger.debug(f'Results returned in order: {[r.result for r in responses]}')


def test_context_manager_cleanup():
    """Verify context manager properly shuts down executor.
    """
    executor = RateLimitedExecutor(max_workers=2, max_per_second=5)

    with executor:
        responses = executor.execute_items(lambda x: x * 2, [1, 2, 3])
        assert all(r.success for r in responses)

    with pytest.raises(RuntimeError):
        executor.submit(lambda: 1)


def test_execute_with_custom_ids():
    """Verify execute() with custom TaskRequest IDs for flexible tracking.
    """
    def process(item):
        return item * 2

    requests = [TaskRequest(item=i, id=('row', i, 'scenario')) for i in range(10)]

    with RateLimitedExecutor(max_workers=5, max_per_second=50) as executor:
        responses = executor.execute(process, requests, desc='Processing')

    assert len(responses) == 10
    for i, response in enumerate(responses):
        assert response.success
        assert response.result == i * 2
        assert response.request.id == ('row', i, 'scenario')

    result_lookup = {r.request.id: r.result for r in responses}
    assert result_lookup[('row', 5, 'scenario')] == 10
    logger.debug(f'Complex IDs preserved: {len(result_lookup)} items')


def test_execute_with_dict_ids():
    """Verify execute() handles dict-based IDs for flexible result organization.
    """
    def process(item):
        value, operation = item
        if operation == 'double':
            return value * 2
        else:
            return value * 3

    requests = [TaskRequest(item=(5, 'double'), id={'row_idx': 0, 'scenario': 'base', 'variant': 'A'}),
                TaskRequest(item=(10, 'triple'), id={'row_idx': 0, 'scenario': 'stressed', 'variant': 'B'}),
                TaskRequest(item=(3, 'double'), id={'row_idx': 1, 'scenario': 'base', 'variant': 'A'}),
                TaskRequest(item=(7, 'triple'), id={'row_idx': 1, 'scenario': 'stressed', 'variant': 'B'})]

    with RateLimitedExecutor(max_workers=5, max_per_second=50) as executor:
        responses = executor.execute(process, requests, desc='Processing')

    result_lookup = {r.request.id['row_idx']: {} for r in responses}
    for response in responses:
        key = (response.request.id['scenario'], response.request.id['variant'])
        result_lookup[response.request.id['row_idx']][key] = response.result

    assert result_lookup[0][('base', 'A')] == 10
    assert result_lookup[0][('stressed', 'B')] == 30
    assert result_lookup[1][('base', 'A')] == 6
    assert result_lookup[1][('stressed', 'B')] == 21
    logger.debug(f'Dict-based ID lookup: {result_lookup}')


def test_execute_items_with_variable_delays():
    """Verify execute_items() returns results in order despite variable completion times.
    """
    def process(item):
        time.sleep(0.01 * (10 - item))
        return item * 2

    items = list(range(10))

    with RateLimitedExecutor(max_workers=5, max_per_second=50) as executor:
        responses = executor.execute_items(process, items, desc='Processing')

    assert len(responses) == 10
    assert all(r.success for r in responses)
    assert [r.result for r in responses] == [i * 2 for i in range(10)]
    logger.debug(f'Ordered results despite delays: {[r.result for r in responses]}')


def test_execute_simple_items():
    """Verify execute() with simple string IDs preserves ID-result mapping.
    """
    def process(item):
        return item * 3

    requests = [TaskRequest(item=i, id=f'id_{i}') for i in range(10)]

    with RateLimitedExecutor(max_workers=5, max_per_second=50) as executor:
        responses = executor.execute(process, requests, desc='Processing')

    assert len(responses) == 10
    for i, response in enumerate(responses):
        assert response.success
        assert response.result == i * 3
        assert response.request.id == f'id_{i}'

    logger.debug(f'Simple IDs preserved: {len(responses)} items')


def test_execute_exception_in_response():
    """Verify execute() captures exceptions without stopping other tasks.
    """
    def failing_process(item):
        if item == 5:
            raise ValueError(f'Cannot process item {item}')
        return item * 2

    items = list(range(10))

    with RateLimitedExecutor(max_workers=5, max_per_second=50) as executor:
        responses = executor.execute_items(failing_process, items, desc='Processing')

    assert len(responses) == 10

    for i, response in enumerate(responses):
        if i == 5:
            assert not response.success
            assert isinstance(response.exception, ValueError)
        else:
            assert response.success
            assert response.result == i * 2


