import abc
import types
import typing as T

from anyio import to_thread
import keyring
import keyrings.alt


class AsyncKeyring(abc.ABC):
    name: str

    @classmethod
    @abc.abstractmethod
    async def priority(cls) -> float: ...

    @classmethod
    async def viable(cls) -> bool:
        return await cls.priority() >= 0

    @abc.abstractmethod
    async def get_password(self, service: str, username: str) -> str | None:
        """Get password of the username for the service"""
        return None

    @abc.abstractmethod
    async def set_password(self, service: str, username: str, password: str) -> None:
        """Set password for the username of the service.

        If the backend cannot store passwords, raise
        PasswordSetError.
        """
        raise keyring.errors.PasswordSetError("Password set not implemented")

    async def delete_password(self, service: str, username: str) -> None:
        """Delete the password for the username of the service.

        If the backend cannot delete passwords, raise
        PasswordDeleteError.
        """
        raise keyring.errors.PasswordDeleteError("Password delete not implemented")

    # Hoping that no implementation of Credential involves IO
    async def get_credential(
        self,
        service: str,
        username: str | None,
    ) -> keyring.credentials.Credential | None: ...


class WrapperKeyring(AsyncKeyring):
    wrap_class: T.ClassVar[type[keyring.backend.KeyringBackend]]
    wrappee: keyring.backend.KeyringBackend

    def __init__(self):
        # All of the implementations Jamie looked at just call set_properties_from_env()
        # So it should be fine to do this in an async context
        self.wrappee = self.wrap_class()
        self.name = self.wrappee.name

    def __repr__(self):
        return f"<{type(self).__name__} {self.wrappee!r}>"

    @classmethod
    async def priority(cls) -> float:
        return await to_thread.run_sync(getattr, cls.wrap_class, "priority")

    @classmethod
    async def viable(cls) -> bool:
        return await to_thread.run_sync(getattr, cls.wrap_class, "viable")

    async def get_password(self, service: str, username: str) -> str | None:
        return await to_thread.run_sync(self.wrappee.get_password, service, username)

    async def set_password(self, service: str, username: str, password: str) -> None:
        return await to_thread.run_sync(
            self.wrappee.set_password, service, username, password
        )

    async def delete_password(self, service: str, username: str) -> None:
        return await to_thread.run_sync(self.wrappee.delete_password, service, username)

    async def get_credential(
        self,
        service: str,
        username: str | None,
    ) -> keyring.credentials.Credential | None:
        return await to_thread.run_sync(self.wrappee.get_credential, service, username)

    @classmethod
    def from_sync(cls, sync: keyring.backend.KeyringBackend) -> type[T.Self]:
        def pop(ns: dict):
            ns["wrap_class"] = sync

        return types.new_class(f"Async{sync.__name__}", (cls,), {}, pop)


async def get_viable_backends() -> list[type[AsyncKeyring]]:
    # This first bit re-implements get_all_keyring() and wraps the results
    await to_thread.run_sync(keyring.backend._load_plugins)
    # get_viable_backends() returns a filter() instance (basically generator),
    # so it does no work initially
    sync_classes = await to_thread.run_sync(
        list, keyring.backend.KeyringBackend.get_viable_backends()
    )

    # These aren't useful here (either because args or we want things to fall through)
    sync_classes.remove(keyring.backends.chainer.ChainerBackend)
    # sync_classes.remove(keyring.backends.null.Keyring)
    sync_classes.remove(keyring.backends.fail.Keyring)
    sync_classes.remove(keyrings.alt.multi.MultipartKeyringWrapper)

    # This is insecure and shouldn't be allowed
    sync_classes.remove(keyrings.alt.file.PlaintextKeyring)

    wrappers = [WrapperKeyring.from_sync(cls) for cls in sync_classes]

    # TODO: Async-native backends

    return wrappers
