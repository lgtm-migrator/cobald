import abc


class ParaSite(abc.ABC):
    """
    Individual provider for a number of indistinguishable resources
    """
    @property
    @abc.abstractmethod
    def supply(self):
        """The volume of resources that is provided by this site"""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def demand(self):
        """The volume of resources to be provided by this site"""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def utilisation(self):
        """Fraction of the provided resources which is actively used"""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def consumption(self):
        """Fraction of the provided resources which is assigned for usage"""
        raise NotImplementedError
