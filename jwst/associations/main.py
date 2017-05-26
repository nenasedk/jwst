from __future__ import print_function

import os
import sys
import argparse
import logging

from jwst.associations import (
    __version__,
    AssociationPool,
    AssociationRegistry,
    generate,
)
from jwst.associations.lib.log_config import (log_config, DMS_config)

# Configure logging
logger = log_config(name=__package__)

# Ruleset names
DISCOVER_RULESET = 'discover'
CANDIDATE_RULESET = 'candidate'


class Main(object):
    """
    Generate Associations from an Association Pool

    Parameters
    ----------
    args: [str, ...], or None
        The command line arguments. Can be one of
            - `None`: `sys.argv` is then used.
            - `[str, ...]`: A list of strings which create the command line
              with the similar structure as `sys.argv`

    pool: None or AssociationPool
        If `None`, a pool file must be specified in the `args`.
        Otherwise, an `AssociationPool`

    Attributes
    ----------
    pool: `AssociationPool`
        The pool read in, or passed in through the parameter `pool`

    rules: `AssociationRegistry`
        The rules used for association creation.

    associations: [`Association`, ...]
        The list of generated associations.

    orphaned: `AssociationPool`
        The pool of exposures that do not belong
        to any association.

    Notes
    -----
    Refer to the :ref:`Association Generator <association-generator>`
    documentation for a full description.
    """

    def __init__(self, args=None, pool=None):

        if args is None:
            args = sys.argv[1:]
        if isinstance(args, str):
            args = args.split(' ')

        parser = argparse.ArgumentParser(
            description='Generate Assocation Data Products',
            usage='asn_generate pool'
        )
        if pool is None:
            parser.add_argument(
                'pool', type=str, help='Association Pool'
            )
        op_group = parser.add_mutually_exclusive_group()
        op_group.add_argument(
            '-i', '--ids', nargs='+',
            dest='asn_candidate_ids',
            help='space-separated list of association candidate IDs to operate on.'
        )
        op_group.add_argument(
            '--discover',
            action='store_true',
            help='Produce discovered associations'
        )
        op_group.add_argument(
            '--all-candidates',
            action='store_true', dest='all_candidates',
            help='Produce all association candidate-specific associations'
        )
        parser.add_argument(
            '-p', '--path', type=str,
            default='.',
            help='Folder to save the associations to. Default: "%(default)s"'
        )
        parser.add_argument(
            '--save-orphans', dest='save_orphans',
            nargs='?', const='orphaned.csv', default=False,
            help='Save orphaned members into the specified table. Default: "%(default)s"'
        )
        parser.add_argument(
            '--version-id', dest='version_id',
            nargs='?', const=True, default=None,
            help=(
                'Version tag to add into association name and products.'
                ' If not specified, no version will be used.'
                ' If specified without a value, the current time is used.'
                ' Otherwise, the specified string will be used.'
            )
        )
        parser.add_argument(
            '-r', '--rules', action='append',
            help='Association Rules file.'
        )
        parser.add_argument(
            '--ignore-default', action='store_true',
            help='Do not include default rules. -r should be used if set.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true', dest='dry_run',
            help='Execute but do not save results.'
        )
        parser.add_argument(
            '-d', '--delimiter', type=str,
            default='|',
            help='''Delimiter
            to use if pool files are comma-separated-value
            (csv) type files. Default: "%(default)s"
            '''
        )
        parser.add_argument(
            '--pool-format', type=str,
            default='ascii',
            help=(
                'Format of the pool file.'
                ' Any format allowed by the astropy'
                ' Unified File I/O interface is allowed.'
                ' Default: "%(default)s"'
            )
        )
        parser.add_argument(
            '-v', '--verbose',
            action='store_const', dest='loglevel',
            const=logging.INFO, default=logging.NOTSET,
            help='Output progress and results.'
        )
        parser.add_argument(
            '-D', '--debug',
            action='store_const', dest='loglevel',
            const=logging.DEBUG,
            help='Output detailed debugging information.'
        )
        parser.add_argument(
            '--DMS',
            action='store_true', dest='DMS_enabled',
            help='Running under DMS workflow conditions.'
        )
        parser.add_argument(
            '--format',
            default='json',
            help='Format of the association files. Default: "%(default)s"'
        )
        parser.add_argument(
            '--version', action='version',
            version='%(prog)s {}'.format(__version__),
            help='Version of the generator.'
        )

        parsed = parser.parse_args(args=args)

        # Configure logging
        config = None
        if parsed.DMS_enabled:
            config = DMS_config
        logger = log_config(name=__package__, config=config)
        logger.setLevel(parsed.loglevel)

        # Preamble
        logger.info('Command-line arguments: {}'.format(args))
        logger.context.set('asn_candidate_ids', parsed.asn_candidate_ids)

        if pool is None:
            logger.info('Reading pool {}'.format(parsed.pool))
            self.pool = AssociationPool.read(
                parsed.pool, delimiter=parsed.delimiter,
                format=parsed.pool_format,
            )
        else:
            self.pool = pool

        # DMS: Add further info to logging.
        try:
            logger.context.set('program', self.pool[0]['PROGRAM'])
        except KeyError:
            pass

        # Setup rules.
        global_constraints = {}

        # Determine mode of operation. Options are
        #  1) Only specified candidates
        #  2) Only discovered assocations that do not match
        #     candidate associations
        #  3) Both discovered and all candidate associations.
        logger.info('Reading rules.')
        if not parsed.discover and\
           not parsed.all_candidates and\
           parsed.asn_candidate_ids is None:
            parsed.discover = True
            parsed.all_candidates = True
        if parsed.discover or parsed.all_candidates:
            global_constraints['asn_candidate'] = constrain_on_candidates(
                None
            )
        elif parsed.asn_candidate_ids is not None:
            global_constraints['asn_candidate'] = constrain_on_candidates(
                parsed.asn_candidate_ids
            )

        self.rules = AssociationRegistry(
            parsed.rules,
            include_default=not parsed.ignore_default,
            global_constraints=global_constraints,
            name=CANDIDATE_RULESET
        )

        if parsed.discover:
            self.rules.update(
                AssociationRegistry(
                    parsed.rules,
                    include_default=not parsed.ignore_default,
                    name=DISCOVER_RULESET
                )
            )

        logger.info('Generating associations.')
        self.associations, self.orphaned = generate(
            self.pool, self.rules, version_id=parsed.version_id
        )

        if parsed.discover:
            self.associations = filter_discovered_only(
                self.associations,
                DISCOVER_RULESET,
                CANDIDATE_RULESET,
                keep_candidates=parsed.all_candidates,
            )
            self.rules.Utility.resequence(self.associations)

        logger.info(self.__str__())

        if not parsed.dry_run:
            self.save(
                path=parsed.path,
                format=parsed.format,
                save_orphans=parsed.save_orphans
            )

    def __str__(self):
        result = []
        result.append((
            'There where {:d} associations '
            'and {:d} orphaned members found.\n'
            'Associations found are:'
        ).format(len(self.associations), len(self.orphaned)))
        for assocs in self.associations:
            result.append(assocs.__str__())

        return '\n'.join(result)

    def save(self, path='.', format='json', save_orphans=False):
        """Save the associations to disk.

        Parameters
        ----------
        path: str
            The path to save the associations to.

        format: str
            The format of the associations

        save_orphans: bool
            If true, save the orphans to an astropy.table.Table
        """
        for asn in self.associations:
            (fname, serialized) = asn.dump(format=format)
            with open(os.path.join(path, fname + '.' + format), 'w') as f:
                f.write(serialized)

        if save_orphans:
            self.orphaned.write(
                os.path.join(path, save_orphans),
                format='ascii',
                delimiter='|'
            )


# #########
# Utilities
# #########
def constrain_on_candidates(candidates):
    """Create a constraint based on a list of candidates

    Parameters
    ----------
    candidates: (str, ...) or None
        List of candidate id's.
        If None, then all candidates are matched.
    """
    constraint = {}
    if candidates is not None and len(candidates):
        c_list = '|'.join(candidates)
        values = ''.join([
            '.+(', c_list, ').+'
        ])
    else:
        values = None
    constraint = {
        'value': values,
        'inputs': ['asn_candidate'],
        'force_unique': True,
        'is_acid': True,
        'evaluate': True,
    }

    return constraint


def filter_discovered_only(
        associations,
        discover_ruleset,
        candidate_ruleset,
        keep_candidates=True,
):
    """Return only those associations that have multiple candidates

    Parameters
    ----------
    associations: iterable
        The list of associations to check. The list
        is that returned by the `generate` function.

    discover_ruleset: str
        The name of the ruleset that has the discover rules

    candidate_ruleset: str
        The name of the ruleset that finds just candidates

    keep_candidates: bool
        Keep explicit candidate associations in the list.

    Returns
    -------
    iterable
        The new list of just cross candidate associations.

    Notes
    -----
    This utility is only meant to run on associations that have
    been constructed. Associations that have been Association.dump
    and then Association.load will not return proper results.
    """
    # Split the associations along discovered/not discovered lines
    asn_by_ruleset = {
        candidate_ruleset: [],
        discover_ruleset: []
    }
    for asn in associations:
        asn_by_ruleset[asn.registry.name].append(asn)
    candidate_list = asn_by_ruleset[candidate_ruleset]
    discover_list = asn_by_ruleset[discover_ruleset]

    # Filter out the non-unique discovereds.
    for candidate in candidate_list:
        if len(discover_list) == 0:
            break
        unique_list = []
        for discover in discover_list:
            if discover != candidate:
                unique_list.append(discover)

        # Reset the discovered list to the new unique list
        # and try the next candidate.
        discover_list = unique_list

    if keep_candidates:
        discover_list.extend(candidate_list)
    return discover_list




if __name__ == '__main__':
    Main()
