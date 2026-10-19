"""Place an order as an event-driven workflow, the way an orchestrator does.

The API answers at once: it writes the order as ``pending``, records a workflow
with its steps in the orchestrator's own database, and publishes the first
step's event. A worker consumes the events one by one; each step does its
part in the company database, then publishes the event of the next step. The
events stay thin (``{workflow_id, type}``): what a step needs is read from the
databases, not carried in the message.
"""
