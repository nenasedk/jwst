"""Association attributes common to DMS-based Rules"""
from .counter import Counter

from jwst.associations.exceptions import (
    AssociationNotAConstraint,
    AssociationNotValidError,
)
from jwst.associations.lib.acid import ACIDMixin
from jwst.associations.lib.constraint import (Constraint, AttrConstraint)
from jwst.associations.lib.utilities import getattr_from_list


__all__ = ['Constraint_TSO', 'DMSBaseMixin']

# Default product name
PRODUCT_NAME_DEFAULT = 'undefined'

# DMS file name templates
_ASN_NAME_TEMPLATE_STAMP = 'jw{program}-{acid}_{stamp}_{type}_{sequence:03d}_asn'
_ASN_NAME_TEMPLATE = 'jw{program}-{acid}_{type}_{sequence:03d}_asn'

# Acquistions and Confirmation images
ACQ_EXP_TYPES = (
    'mir_tacq',
    'nis_taconfirm',
    'nis_tacq',
    'nrc_taconfirm',
    'nrc_tacq',
    'nrs_confirm',
    'nrs_msata',
    'nrs_taconfirm',
    'nrs_tacq',
    'nrs_taslit',
    'nrs_wata',
)

# Exposure EXP_TYPE to Association EXPTYPE mapping
EXPTYPE_MAP = {
    'mir_darkall':       'dark',
    'mir_darkimg':       'dark',
    'mir_darkmrs':       'dark',
    'mir_flatimage':     'flat',
    'mir_flatmrs':       'flat',
    'mir_flatimage-ext': 'flat',
    'mir_flatmrs-ext':   'flat',
    'mir_tacq':          'target_acquisition',
    'nis_dark':          'dark',
    'nis_focus':         'engineering',
    'nis_lamp':          'engineering',
    'nis_tacq':          'target_acquisition',
    'nis_taconfirm':     'target_acquisition',
    'nrc_dark':          'dark',
    'nrc_flat':          'flat',
    'nrc_focus':         'engineering',
    'nrc_led':           'engineering',
    'nrc_tacq':          'target_acquisition',
    'nrc_taconfirm':     'target_acquisition',
    'nrs_autoflat':      'autoflat',
    'nrs_autowave':      'autowave',
    'nrs_confirm':       'target_acquisition',
    'nrs_dark':          'dark',
    'nrs_focus':         'engineering',
    'nrs_image':         'engineering',
    'nrs_lamp':          'engineering',
    'nrs_msata':         'target_acquisition',
    'nrs_tacq':          'target_acquisition',
    'nrs_taconfirm':     'target_acquisition',
    'nrs_taslit':        'target_acquisition',
    'nrs_wata':          'target_acquisition',
}

# Coronographic exposures
CORON_EXP_TYPES = [
    'mir_lyot',
    'mir_4qpm',
    'nrc_coron'
]

# Exposures that get Level2b processing
IMAGE2_SCIENCE_EXP_TYPES = [
    'mir_image',
    'mir_lyot',
    'mir_4qpm',
    'nis_ami',
    'nis_image',
    'nrc_image',
    'nrc_coron',
    'nrc_tsimage',
]

IMAGE2_NONSCIENCE_EXP_TYPES = [
    'mir_coroncal',
    'nis_focus',
    'nrc_focus',
    'nrs_focus',
    'nrs_image',
    'nrs_mimf',
]
IMAGE2_NONSCIENCE_EXP_TYPES.extend(ACQ_EXP_TYPES)

SPEC2_SCIENCE_EXP_TYPES = [
    'nrc_tsgrism',
    'nrc_wfss',
    'mir_lrs-fixedslit',
    'mir_lrs-slitless',
    'mir_mrs',
    'nrs_fixedslit',
    'nrs_ifu',
    'nrs_msaspec',
    'nrs_brightobj',
    'nis_soss',
    'nis_wfss',
]

SPECIAL_EXPTYPES = {
    'psf': ['is_psf'],
    'imprint': ['is_imprt'],
    'background': ['bkgdtarg']
}

# Exposures that are always TSO
TSO_EXP_TYPES = [
    'nrc_tsimage',
    'nrc_tsgrism',
    'nrs_brightobj'
]

# Key that uniquely identfies members.
MEMBER_KEY = 'expname'

# Non-specified values found in DMS Association Pools
_EMPTY = (None, '', 'NULL', 'Null', 'null', '--', 'N', 'n', 'F', 'f', 'N/A', 'n/a')

# Degraded status information
_DEGRADED_STATUS_OK = (
    'No known degraded exposures in association.'
)
_DEGRADED_STATUS_NOTOK = (
    'One or more members have an error associated with them.'
    '\nDetails can be found in the member.exposerr attribute.'
)


class DMSBaseMixin(ACIDMixin):
    """Association attributes common to DMS-based Rules

    Attributes
    ----------
    from_items : [item[,...]]
        The list of items that contributed to the association.

    sequence : int
        The sequence number of the current association
    """

    # Associations of the same type are sequenced.
    _sequence = Counter(start=1)

    def __init__(self, *args, **kwargs):
        super(DMSBaseMixin, self).__init__(*args, **kwargs)

        self._acid = None
        self.sequence = None
        if 'degraded_status' not in self.data:
            self.data['degraded_status'] = _DEGRADED_STATUS_OK
        if 'program' not in self.data:
            self.data['program'] = 'noprogram'

    @classmethod
    def create(cls, item, version_id=None):
        """Create association if item belongs

        Parameters
        ----------
        item : dict
            The item to initialize the association with.

        version_id : str or None
            Version_Id to use in the name of this association.
            If None, nothing is added.

        Returns
        -------
        (association, reprocess_list)
            2-tuple consisting of:

                - association : The association or, if the item does not
                  match this rule, None
                - [ProcessList[, ...]]: List of items to process again.
        """
        asn, reprocess = super(DMSBaseMixin, cls).create(item, version_id)
        if not asn:
            return None, reprocess
        asn.sequence = next(asn._sequence)
        return asn, reprocess

    @property
    def acid(self):
        """Association ID"""
        acid = self._acid
        if self._acid is None:
            acid = self.acid_from_constraints()
        return acid

    @property
    def asn_name(self):
        program = self.data['program']
        version_id = self.version_id
        asn_type = self.data['asn_type']
        sequence = self.sequence

        if version_id:
            name = _ASN_NAME_TEMPLATE_STAMP.format(
                program=program,
                acid=self.acid.id,
                stamp=version_id,
                type=asn_type,
                sequence=sequence,
            )
        else:
            name = _ASN_NAME_TEMPLATE.format(
                program=program,
                acid=self.acid.id,
                type=asn_type,
                sequence=sequence,
            )
        return name.lower()

    @property
    def current_product(self):
        return self.data['products'][-1]

    @property
    def from_items(self):
        """List of items from which members were created"""
        try:
            items = [
                member.item
                for product in self['products']
                for member in product['members']
            ]
        except KeyError:
            items = []
        return items

    @property
    def member_ids(self):
        """Set of all member ids in all products of this association"""
        member_ids = set(
            member[MEMBER_KEY]
            for product in self['products']
            for member in product['members']
        )
        return member_ids

    @property
    def validity(self):
        """Keeper of the validity tests"""
        try:
            validity = self._validity
        except AttributeError:
            self._validity = {}
            validity = self._validity
        return validity

    @validity.setter
    def validity(self, item):
        """Set validity dict"""
        self._validity = item

    def get_exposure_type(self, item, default='science'):
        """Determine the exposure type of a pool item

        Parameters
        ----------
        item : dict
            The pool entry to determine the exposure type of

        default : str or None
            The default exposure type.
            If None, routine will raise LookupError

        Returns
        -------
        exposure_type : str
            Exposure type. Can be one of

                - 'science': Item contains science data
                - 'target_aquisition': Item contains target acquisition data.
                - 'autoflat': NIRSpec AUTOFLAT
                - 'autowave': NIRSpec AUTOWAVE
                - 'psf': PSF
                - 'imprint': MSA/IFU Imprint/Leakcal

        Raises
        ------
        LookupError
            When `default` is None and an exposure type cannot be determined
        """
        result = default

        # Base type off of exposure type.
        try:
            exp_type = item['exp_type']
        except KeyError:
            raise LookupError('Exposure type cannot be determined')

        result = EXPTYPE_MAP.get(exp_type, default)

        if result is None:
            raise LookupError('Cannot determine exposure type')

        # For `science` data, compare against special modifiers
        # to further refine the type.
        if result == 'science':
            for special, source in SPECIAL_EXPTYPES.items():
                try:
                    self.item_getattr(item, source)
                except KeyError:
                    pass
                else:
                    result = special
                    break

        return result

    def is_member(self, new_member):
        """Check if member is already a member

        Parameters
        ----------
        new_member : Member
            The member to check for
        """
        try:
            current_members = self.current_product['members']
        except KeyError:
            return False

        for member in current_members:
            if member == new_member:
                return True
        return False

    def is_item_member(self, item):
        """Check if item is already a member of this association

        Parameters
        ----------
        item : dict
            The item to check for.

        Returns
        -------
        is_item_member : bool
            True if item is a member.
        """
        return item in self.from_items

    def is_item_tso(self, item, other_exp_types=None):
        """Is the given item TSO

        Determine whether the specific item represents
        TSO data or not. When used to determine naming
        of files, coronagraphic data will be included through
        the `other_exp_types` parameter.

        Parameters
        ----------
        item : dict
            The item to check for.

        other_exp_types: [str[,...]] or None
            List of other exposure types to consider TSO.

        Returns
        -------
        is_item_tso : bool
            Item represents a TSO exposure.
        """
        # If not a science exposure, such as target aquisitions,
        # then other TSO indicators do not apply.
        if item['pntgtype'] != 'science':
            return False

        # Setup exposure list
        all_exp_types = TSO_EXP_TYPES.copy()
        if other_exp_types:
            all_exp_types += other_exp_types

        # Go through all other TSO indicators.
        try:
            is_tso = self.constraints['is_tso'].value == 't'
        except (AttributeError, KeyError):
            # No such constraint is defined. Just continue on.
            is_tso = False
        try:
            is_tso = is_tso or self.item_getattr(item, ['tsovisit'])[1] == 't'
        except KeyError:
            pass
        try:
            is_tso = is_tso or self.item_getattr(item, ['exp_type'])[1] in all_exp_types
        except KeyError:
            pass
        return is_tso

    def item_getattr(self, item, attributes):
        """Return value from any of a list of attributes

        Parameters
        ----------
        item : dict
            item to retrieve from

        attributes : list
            List of attributes

        Returns
        -------
        (attribute, value)
            Returns the value and the attribute from
            which the value was taken.

        Raises
        ------
        KeyError
            None of the attributes are found in the dict.
        """
        return getattr_from_list(
            item,
            attributes,
            invalid_values=self.INVALID_VALUES
        )

    def new_product(self, product_name=PRODUCT_NAME_DEFAULT):
        """Start a new product"""
        product = {
            'name': product_name,
            'members': []
        }
        try:
            self.data['products'].append(product)
        except (AttributeError, KeyError):
            self.data['products'] = [product]

    def update_asn(self, item=None, member=None):
        """Update association meta information

        Parameters
        ----------
        item : dict or None
            Item to use as a source. If not given, item-specific
            information will be left unchanged.

        member : Member or None
            An association member to use as source.
            If not given, member-specific information will be update
            from current association/product membership.

        Notes
        -----
        If both `item` and `member` are given,
        information in `member` will take precedence.
        """
        self.update_degraded_status()

    def update_degraded_status(self):
        """Update association degraded status"""

        if self.data['degraded_status'] == _DEGRADED_STATUS_OK:
            for product in self.data['products']:
                for member in product['members']:
                    try:
                        exposerr = member['exposerr']
                    except KeyError:
                        continue
                    else:
                        if exposerr not in _EMPTY:
                            self.data['degraded_status'] = _DEGRADED_STATUS_NOTOK
                            break

    def update_validity(self, entry):
        for test in self.validity.values():
            if not test['validated']:
                test['validated'] = test['check'](entry)

    @classmethod
    def reset_sequence(cls):
        cls._sequence = Counter(start=1)

    @classmethod
    def validate(cls, asn):
        super(DMSBaseMixin, cls).validate(asn)

        if isinstance(asn, DMSBaseMixin):
            result = False
            try:
                result = all(
                    test['validated']
                    for test in asn.validity.values()
                )
            except (AttributeError, KeyError):
                raise AssociationNotValidError('Validation failed')
            if not result:
                raise AssociationNotValidError(
                    'Validation failed validity tests.'
                )

        return True

    def _get_exposure(self):
        """Get string representation of the exposure id

        Returns
        -------
        exposure : str
            The Level3 Product name representation
            of the exposure & activity id.
        """
        exposure = ''
        try:
            activity_id = format_list(
                self.constraints['activity_id'].found_values
            )
        except KeyError:
            pass
        else:
            if activity_id not in _EMPTY:
                exposure = '{0:0>2s}'.format(activity_id)
        return exposure

    def _get_instrument(self):
        """Get string representation of the instrument

        Returns
        -------
        instrument : str
            The Level3 Product name representation
            of the instrument
        """
        instrument = format_list(self.constraints['instrument'].found_values)
        return instrument

    def _get_opt_element(self):
        """Get string representation of the optical elements

        Returns
        -------
        opt_elem : str
            The Level3 Product name representation
            of the optical elements.
        """
        # Retrieve all the optical elements
        opt_elems = []
        for opt_elem in ['opt_elem', 'opt_elem2', 'opt_elem3']:
            try:
                values = list(self.constraints[opt_elem].found_values)
            except KeyError:
                pass
            else:
                values.sort(key=str.lower)
                value = format_list(values)
                if value not in _EMPTY:
                    opt_elems.append(value)

        # Build the string. Sort the elements in order to
        # create data-independent results
        opt_elems.sort(key=str.lower)
        opt_elem = '-'.join(opt_elems)
        if opt_elem == '':
            opt_elem = 'clear'

        return opt_elem

    def _get_subarray(self):
        """Get string representation of the subarray

        Returns
        -------
        subarray : str
            The Level3 Product name representation
            of the subarray.
        """
        result = ''
        try:
            subarray = format_list(self.constraints['subarray'].found_values)
        except KeyError:
            subarray = None
        if subarray == 'full':
            subarray = None
        if subarray is not None:
            result = subarray

        return result

    def _get_target(self):
        """Get string representation of the target

        Returns
        -------
        target : str
            The Level3 Product name representation
            of the target or source ID.
        """
        target_id = format_list(self.constraints['target'].found_values)
        target = 't{0:0>3s}'.format(str(target_id))
        return target


# -----------------
# Basic constraints
# -----------------
class DMSAttrConstraint(AttrConstraint):
    """DMS-focused attribute constraint

    Forces definition of invalid values
    """
    def __init__(self, **kwargs):

        if kwargs.get('invalid_values', None) is None:
            kwargs['invalid_values'] = _EMPTY

        super(DMSAttrConstraint, self).__init__(**kwargs)


class Constraint_TSO(Constraint):
    """Match on Time-Series Observations"""
    def __init__(self, *args, **kwargs):
        super(Constraint_TSO, self).__init__(
            [
                DMSAttrConstraint(
                    sources=['pntgtype'],
                    value='science'
                ),
                Constraint(
                    [
                        DMSAttrConstraint(
                            sources=['tsovisit'],
                            value='t',
                        ),
                        DMSAttrConstraint(
                            sources=['exp_type'],
                            value='|'.join(TSO_EXP_TYPES),
                        ),
                    ],
                    reduce=Constraint.any
                )
            ],
            name='is_tso'
        )


# #########
# Utilities
# #########
def format_list(alist):
    """Format a list according to DMS naming specs"""
    return '-'.join(alist)
