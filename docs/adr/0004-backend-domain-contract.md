# Backend domain contract

The Pi owns all patient state. Immutable encrypted revisions carry clinical values;
normal columns carry bounded routing/provenance metadata. Source identity is keyed,
versioned and namespace-bound. Current pointers can advance without destroying old
evidence. Clinical dates retain acquisition semantics and never become upload dates.

Manual weight, pulmonary entry, journal and reviewed PDF workflows are independent
of optional native integrations. Unverified adapters remain disabled. Calculation
methods use Decimal and exact revision manifests. Every read authorizes before
unwrapping; every mutation checks concurrency again at commit.
