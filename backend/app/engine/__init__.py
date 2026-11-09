"""
Singleton instances for DBMS Coordinator and Simulation Runner.
"""
from app.engine.coordinator import DBMSTransactionCoordinator
from app.fl.client_simulator import ClientSimulationManager

# Global singleton coordinator
coordinator = DBMSTransactionCoordinator()

# Global singleton client simulator
simulator = ClientSimulationManager()
