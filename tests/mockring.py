"""
Mock Keyring
"""

from swiss_army_upload.junk_drawer import keyring


class MockKeyring(keyring.AsyncKeyring):
    name = "Mock Keyring"

    creds: dict[tuple[str, str], str]

    def __init__(self):
        self.creds = {}

    @classmethod
    async def priority(cls) -> float:
        return 10

    async def get_password(self, service: str, username: str) -> str | None:
        """Get password of the username for the service"""
        return self.creds.get((service, username), None)

    async def set_password(self, service: str, username: str, password: str) -> None:
        """Set password for the username of the service.

        If the backend cannot store passwords, raise
        PasswordSetError.
        """
        self.creds[service, username] = password

    async def delete_password(self, service: str, username: str) -> None:
        """Delete the password for the username of the service.

        If the backend cannot delete passwords, raise
        PasswordDeleteError.
        """
        self.creds.pop((service, username), None)

    async def get_credential(
        self,
        service: str,
        username: str | None,
    ) -> keyring.credentials.Credential | None:
        if username is not None:
            password = await self.get_password(service, username)
            if password is None:
                return None
            else:
                return keyring.credentials.SimpleCredential(username, password)
        else:
            for (serv, user), pword in self.creds.items():
                if serv == service:
                    return keyring.credentials.SimpleCredential(user, pword)
            else:
                return None
