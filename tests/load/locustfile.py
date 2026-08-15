"""Locust load testing suite for ContractIQ RAG query throughput and latency profiling."""

import random

from locust import HttpUser, between, task

SAMPLE_QUERIES = [
    "What is the liability cap under the Master Services Agreement?",
    "What are the payment terms and invoicing schedule in the Statement of Work?",
    "What is the notice period required for contract termination?",
    "Are there any auto-renewal provisions in the vendor agreement?",
    "What confidential information is protected under the Non-Disclosure Agreement?",
    "What are the insurance coverage requirements for the provider?",
    "What is the governing law and dispute resolution jurisdiction?",
    "What are the base rent terms and security deposit amounts in the lease?",
]


class ContractIQUser(HttpUser):
    """Simulates realistic concurrent user interactions against ContractIQ."""

    wait_time = between(1, 3)

    @task(4)
    def query_contract(self):
        """Simulate primary RAG query workload."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/api/v1/query",
            json={
                "query": query,
                "top_k": 5,
                "stream": False,
            },
            name="/api/v1/query",
        )

    @task(2)
    def list_documents(self):
        """Simulate document repository listing."""
        self.client.get("/api/v1/documents", name="/api/v1/documents")

    @task(1)
    def check_health(self):
        """Simulate infrastructure health checking."""
        self.client.get("/health", name="/health")

    @task(1)
    def get_analytics(self):
        """Simulate analytics dashboard polling."""
        self.client.get("/api/v1/analytics/usage", name="/api/v1/analytics/usage")
