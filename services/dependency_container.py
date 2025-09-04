from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, TypeVar, Type, Optional, get_type_hints
import inspect
import logging
from functools import wraps


T = TypeVar('T')


class ServiceLifetime:
    """Service lifetime constants"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceDescriptor:
    """Describes how a service should be created and managed"""
    
    def __init__(self, service_type: Type, implementation: Type, 
                 lifetime: str = ServiceLifetime.TRANSIENT, factory: Optional[Callable] = None):
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self.instance = None


class IDependencyContainer(ABC):
    """Interface for dependency injection container"""
    
    @abstractmethod
    def register(self, service_type: Type[T], implementation: Type[T], 
                lifetime: str = ServiceLifetime.TRANSIENT) -> None:
        pass
    
    @abstractmethod
    def register_singleton(self, service_type: Type[T], implementation: Type[T]) -> None:
        pass
    
    @abstractmethod
    def register_factory(self, service_type: Type[T], factory: Callable[[], T], 
                        lifetime: str = ServiceLifetime.TRANSIENT) -> None:
        pass
    
    @abstractmethod
    def resolve(self, service_type: Type[T]) -> T:
        pass
    
    @abstractmethod
    def is_registered(self, service_type: Type) -> bool:
        pass


class DependencyContainer(IDependencyContainer):
    """Simple dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, service_type: Type[T], implementation: Type[T], 
                lifetime: str = ServiceLifetime.TRANSIENT) -> None:
        """Register a service with its implementation"""
        if not issubclass(implementation, service_type):
            raise ValueError(f"{implementation} must implement {service_type}")
        
        descriptor = ServiceDescriptor(service_type, implementation, lifetime)
        self._services[service_type] = descriptor
        
        self.logger.debug(f"Registered {service_type.__name__} -> {implementation.__name__} ({lifetime})")
    
    def register_singleton(self, service_type: Type[T], implementation: Type[T]) -> None:
        """Register a singleton service"""
        self.register(service_type, implementation, ServiceLifetime.SINGLETON)
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T], 
                        lifetime: str = ServiceLifetime.TRANSIENT) -> None:
        """Register a service with a factory function"""
        descriptor = ServiceDescriptor(service_type, service_type, lifetime, factory)
        self._services[service_type] = descriptor
        
        self.logger.debug(f"Registered factory for {service_type.__name__} ({lifetime})")
    
    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register a specific instance as singleton"""
        descriptor = ServiceDescriptor(service_type, type(instance), ServiceLifetime.SINGLETON)
        descriptor.instance = instance
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance
        
        self.logger.debug(f"Registered instance for {service_type.__name__}")
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} is not registered")
        
        descriptor = self._services[service_type]
        
        # Handle singleton
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
            
            instance = self._create_instance(descriptor)
            self._singletons[service_type] = instance
            return instance
        
        # Handle scoped
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]
            
            instance = self._create_instance(descriptor)
            self._scoped_instances[service_type] = instance
            return instance
        
        # Handle transient
        else:
            return self._create_instance(descriptor)
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance using the descriptor"""
        try:
            # Use factory if available
            if descriptor.factory:
                return descriptor.factory()
            
            # Use constructor injection
            return self._create_with_injection(descriptor.implementation)
            
        except Exception as e:
            self.logger.error(f"Failed to create instance of {descriptor.implementation.__name__}: {e}")
            raise
    
    def _create_with_injection(self, implementation: Type) -> Any:
        """Create instance with constructor dependency injection"""
        # Get constructor signature
        constructor = implementation.__init__
        signature = inspect.signature(constructor)
        
        # Prepare arguments for constructor
        kwargs = {}
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            # Try to resolve parameter type
            param_type = param.annotation
            if param_type != inspect.Parameter.empty and self.is_registered(param_type):
                kwargs[param_name] = self.resolve(param_type)
            elif param.default != inspect.Parameter.empty:
                # Use default value if available
                kwargs[param_name] = param.default
            else:
                # Try to resolve by parameter name (convention-based)
                if hasattr(self, f'_resolve_{param_name}'):
                    resolver = getattr(self, f'_resolve_{param_name}')
                    kwargs[param_name] = resolver()
        
        return implementation(**kwargs)
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered"""
        return service_type in self._services
    
    def clear_scoped(self) -> None:
        """Clear scoped instances (useful for request scoping)"""
        self._scoped_instances.clear()
        self.logger.debug("Cleared scoped instances")
    
    def get_registered_services(self) -> Dict[str, str]:
        """Get list of registered services for debugging"""
        return {
            service_type.__name__: f"{descriptor.implementation.__name__} ({descriptor.lifetime})"
            for service_type, descriptor in self._services.items()
        }


def inject(container: IDependencyContainer):
    """Decorator for method injection"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            signature = inspect.signature(func)
            
            # Resolve dependencies
            for param_name, param in signature.parameters.items():
                if param_name not in kwargs and param.annotation != inspect.Parameter.empty:
                    param_type = param.annotation
                    if container.is_registered(param_type):
                        kwargs[param_name] = container.resolve(param_type)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ServiceProvider:
    """Service provider for easier service registration"""
    
    def __init__(self, container: IDependencyContainer):
        self.container = container
        self.logger = logging.getLogger(__name__)
    
    def configure_core_services(self):
        """Configure core application services"""
        from config_manager import ConfigManager, AppConfig
        from database import Database
        from json_storage import JSONStorage
        from handlers.ai.ai_handler import AIHandler
        from reminder_scheduler import ReminderScheduler
        from repeat_handler import RepeatHandler
        from notification_strategies import NotificationStrategyFactory, NotificationContext
        from utils.logger import LogManager
        
        # Configuration
        config_manager = ConfigManager()
        app_config = config_manager.load_config()
        
        self.container.register_instance(AppConfig, app_config)
        self.container.register_singleton(ConfigManager, ConfigManager)
        
        # Core services
        self.container.register_factory(
            Database, 
            lambda: Database(app_config.database.path),
            ServiceLifetime.SINGLETON
        )
        
        self.container.register_factory(
            JSONStorage,
            lambda: JSONStorage(app_config.storage.users_path),
            ServiceLifetime.SINGLETON
        )
        
        self.container.register_factory(
            AIHandler,
            lambda: AIHandler(app_config.ai.openrouter_key),
            ServiceLifetime.SINGLETON
        )
        
        self.container.register_singleton(RepeatHandler, RepeatHandler)
        
        # Logging service
        self.container.register_singleton(LogManager, LogManager)
        
        # Notification services
        self.container.register_factory(
            NotificationContext,
            lambda: NotificationContext(
                NotificationStrategyFactory.create(app_config.notification.strategy)
            ),
            ServiceLifetime.SINGLETON
        )
        
        self.logger.info("Core services configured")
    
    def configure_handlers(self):
        """Configure message and callback handlers"""
        from message_handlers import ReminderMessageHandler
        from callback_handlers import ReminderCallbackHandler
        
        # These will be resolved with dependency injection
        self.container.register(ReminderMessageHandler, ReminderMessageHandler, ServiceLifetime.SCOPED)
        self.container.register(ReminderCallbackHandler, ReminderCallbackHandler, ServiceLifetime.SCOPED)
        
        self.logger.info("Handlers configured")


# Global container instance
container = DependencyContainer()
service_provider = ServiceProvider(container)
