# -*- coding: utf-8 -*-
# Copyright (c) 2017 Ian Cordasco
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module containing the validation logic for rfc3986."""
from . import exceptions
from . import misc
from . import normalizers


class Validator(object):
    """Object used to configure validation of all objects in rfc3986.

    Example usage:

    .. code-block:: python

        >>> uri = rfc3986.uri_reference('https://github.com/')
        >>> validator = rfc3986.Validator().require_components(
        ...    'scheme', 'host', 'path',
        ... ).allow_schemes(
        ...    'http', 'https',
        ... ).allow_hosts(
        ...    '127.0.0.1', 'github.com',
        ... )
        ...
        >>> validator.validate(uri)
        >>> invalid_uri = rfc3986.uri_reference('imap://mail.google.com')
        >>> validator.validate(invalid_uri)
        Traceback (most recent call last):
        ...
        ValidationErrors("Invalid scheme", "Missing path")

    """

    COMPONENT_NAMES = frozenset([
        'scheme',
        'userinfo',
        'host',
        'port',
        'path',
        'query',
        'fragment',
    ])

    def __init__(self):
        """Initialize our default validations."""
        self.allowed_schemes = set()
        self.allowed_hosts = set()
        self.allowed_ports = set()
        self.allow_password = True
        self.require_presence_of = {
            'scheme': False,
            'userinfo': False,
            'host': False,
            'port': False,
            'path': False,
            'query': False,
            'fragment': False,
        }

    def allow_schemes(self, *schemes):
        """Require the scheme to be one of the provided schemes.

        :param schemes:
            Schemes, without ``://`` that are allowed.
        :returns:
            The validator instance.
        :rtype:
            Validator
        """
        for scheme in schemes:
            self.allowed_schemes.add(normalizers.normalize_scheme(scheme))
        return self

    def allow_hosts(self, *hosts):
        """Require the host to be one of the provided hosts.

        :param hosts:
            Hosts that are allowed.
        :returns:
            The validator instance.
        :rtype:
            Validator
        """
        for host in hosts:
            self.allowed_hosts.add(normalizers.normalize_host(host))
        return self

    def allow_ports(self, *ports):
        """Require the port to be one of the provided ports.

        :param ports:
            Ports that are allowed.
        :returns:
            The validator instance.
        :rtype:
            Validator
        """
        for port in ports:
            port_int = int(port, base=10)
            if 0 <= port_int <= 65535:
                self.allowed_ports.add(port_int)
        return self

    def allow_use_of_password(self):
        """Allow passwords to be present in the URI."""
        self.allow_password = True
        return self

    def forbid_use_of_password(self):
        """Prevent passwords from being included in the URI."""
        self.allow_password = False
        return self

    def require_components(self, *components):
        """Require the components provided.

        :param components:
            Names of components from :attr:`Validator.COMPONENT_NAMES`.
        :returns:
            The validator instance.
        :rtype:
            Validator
        """
        components = [c.lower() for c in components]
        for component in components:
            if component not in self.COMPONENT_NAMES:
                raise ValueError(
                    '"{}" is not a valid component'.format(component)
                )
        self.require_presence_of.update({
            component: True for component in components
        })
        return self

    def validate(self, uri):
        """Check a URI for conditions specified on this validator.

        :param uri:
            Parsed URI to validate.
        :type uri:
            rfc3986.uri.URIReference
        :raises MissingComponentError:
            When a required component is missing.
        :raises UnpermittedComponentError:
            When a component is not one of those allowed.
        :raises PasswordForbidden:
            When a password is present in the userinfo component but is
            not permitted by configuration.
        """
        if not self.allow_password:
            check_password(uri)

        required_components = [
            component
            for component, required in self.require_presence_of.items()
            if required
        ]
        if required_components:
            ensure_required_components_exist(uri, required_components)


def check_password(uri):
    """Assert that there is no password present in the uri."""
    userinfo = uri.userinfo
    if not userinfo:
        return
    credentials = userinfo.split(':', 1)
    if len(credentials) <= 1:
        return
    raise exceptions.PasswordForbidden(uri)


def ensure_required_components_exist(uri, required_components):
    """Assert that all required components are present in the URI."""
    missing_components = sorted([
        component
        for component in required_components
        if getattr(uri, component) is None
    ])
    if missing_components:
        raise exceptions.MissingComponentError(uri, *missing_components)


def is_valid(value, matcher, require):
    """Determine if a value is valid based on the provided matcher.

    :param str value:
        Value to validate.
    :param matcher:
        Compiled regular expression to use to validate the value.
    :param require:
        Whether or not the value is required.
    """
    if require:
        return (value is not None
                and matcher.match(value))

    # require is False and value is not None
    return value is None or matcher.match(value)


def authority_is_valid(authority, host=None, require=False):
    """Determine if the authority string is valid.

    :param str authority:
        The authority to validate.
    :param str host:
        (optional) The host portion of the authority to validate.
    :param bool require:
        (optional) Specify if authority must not be None.
    :returns:
        ``True`` if valid, ``False`` otherwise
    :rtype:
        bool
    """
    validated = is_valid(authority, misc.SUBAUTHORITY_MATCHER, require)
    if validated and host is not None and misc.IPv4_MATCHER.match(host):
        return valid_ipv4_host_address(host)
    return validated


def scheme_is_valid(scheme, require=False):
    """Determine if the scheme is valid.

    :param str scheme:
        The scheme string to validate.
    :param bool require:
        (optional) Set to ``True`` to require the presence of a scheme.
    :returns:
        ``True`` if the scheme is valid. ``False`` otherwise.
    :rtype:
        bool
    """
    return is_valid(scheme, misc.SCHEME_MATCHER, require)


def path_is_valid(path, require=False):
    """Determine if the path component is valid.

    :param str path:
        The path string to validate.
    :param bool require:
        (optional) Set to ``True`` to require the presence of a path.
    :returns:
        ``True`` if the path is valid. ``False`` otherwise.
    :rtype:
        bool
    """
    return is_valid(path, misc.PATH_MATCHER, require)


def query_is_valid(query, require=False):
    """Determine if the query component is valid.

    :param str query:
        The query string to validate.
    :param bool require:
        (optional) Set to ``True`` to require the presence of a query.
    :returns:
        ``True`` if the query is valid. ``False`` otherwise.
    :rtype:
        bool
    """
    return is_valid(query, misc.QUERY_MATCHER, require)


def fragment_is_valid(fragment, require=False):
    """Determine if the fragment component is valid.

    :param str fragment:
        The fragment string to validate.
    :param bool require:
        (optional) Set to ``True`` to require the presence of a fragment.
    :returns:
        ``True`` if the fragment is valid. ``False`` otherwise.
    :rtype:
        bool
    """
    return is_valid(fragment, misc.FRAGMENT_MATCHER, require)


def valid_ipv4_host_address(host):
    """Determine if the given host is a valid IPv4 address."""
    # If the host exists, and it might be IPv4, check each byte in the
    # address.
    return all([0 <= int(byte, base=10) <= 255 for byte in host.split('.')])
