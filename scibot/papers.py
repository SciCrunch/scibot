class KeyAccessor:
    # XXX whenever annos changes these need to be recreated as well...
    # if that is too slow then we will need to implement proper add
    # and delete for only affected items...
    """ For when your identifiers aren't python compatible. """
    prop = 'id'
    object_container_class = set
    def __init__(self, objects=tuple(), id_prop=None):
        self._propagate = issubclass(self.object_container_class, KeyAccessor)
        self._objects = {}
        errors = []
        for o in objects:
            k = getattr(o, self.prop)
            if k not in self._objects:
                self._objects[k] = self._make_cont()

            try:
                self._objects[k].add(o)
            except BaseException as e:
                if errors:
                    try:
                        raise e from errors[-1]
                    except BaseException as ne:
                        errors.append(ne)
                else:
                    errors.append(e)

        if errors:
            raise errors[-1]

        self._id_prop = None
        if id_prop is not None:
            if objects:
                print('setting id prop')
                setattr(self, id_prop, getattr(o, id_prop))  # o from the for loop
            else:
                self._id_prop = id_prop

    def _make_cont(self):
        if self._propagate:
            cont = self.object_container_class(id_prop=self.prop)
        else:
            cont = self.object_container_class()
        return cont

    def remove(self, object_):
        k = getattr(object_, self.prop)
        self._objects[k].remove(object_)
        if not self._objects[k]:
            self._objects.pop(k)

    def discard(self, object_):
        k = getattr(object_, self.prop)
        self._objects[k].discard(object_)
        if not self._objects[k]:
            self._objects.pop(k)

    def add(self, object_):
        if self._id_prop is not None:
            setattr(self, self._id_prop, getattr(object_, self._id_prop))
            self._id_prop = None
        k = getattr(object_, self.prop)
        if k not in self._objects:
            self._objects[k] = self._make_cont()

        self._objects[k].add(object_)

    def keys(self):
        return sorted(self._objects, key=lambda k: '0' if k is None else k)

    def values(self):
        for v in list(self._objects.values()):
            yield v

    def items(self):
        # we use list() here to simplify synchronization issues with the websocket
        # since yield allows the thread to shift
        for k, v in list(self._objects.items()):
            yield k, v

    def __iter__(self):
        for k in self._objects:
            yield k

    def __contains__(self, key):
        return key in self._objects

    def __getitem__(self, key):
        try:
            return self._objects[key]
        except KeyError:
            self.__missing__(key)

    #def __setitem__(self, key):
        #raise TypeError('Cannot set values on this class, it is immutable')

    def __missing__(self, key):
        raise KeyError(f'{key} not found')

    def __len__(self):
        return len(self._objects)

    def __repr__(self):
        return repr({k:v for k,v in self.items()})

    def __str__(self):
        return str({k:v for k,v in self.items()})


class RRIDs(KeyAccessor):
    """ AKA a Paper """
    prop = 'rrid'
    object_container_class = set

    @property
    def doi(self):
        if None in self._objects:
            for o in self._objects[None]:
                if o.KillPageNote:
                    continue
                if o._anno.is_page_note or o.user != 'scibot':  # FIXME some curators did these as annotations too...
                    for t in o.tags:
                        if t.startswith('DOI:') and ' ' not in t and '\n' not in t and t.count(':') == 1:
                            return t

    @property
    def pmid(self):
        if None in self._objects:
            for o in self._objects[None]:
                if o.KillPageNote:
                    continue
                for t in o.tags:
                    if t.startswith('PMID:') and ' ' not in t and '\n' not in t and t.count(':') == 1:
                        return t


class Papers(KeyAccessor):
    prop = 'uri_normalized'
    object_container_class = RRIDs


class SameDOI(KeyAccessor):
    prop = 'doi'
    object_container_class = Papers


class SamePMID(KeyAccessor):
    prop = 'pmid'
    object_container_class = Papers


class MultiplePMID(KeyAccessor):
    prop = 'doi'
    object_container_class = SamePMID


class MultipleDOI(KeyAccessor):
    prop = 'pmid'
    object_container_class = SameDOI


class RRIDSimple(KeyAccessor):
    prop = 'rrid'
    object_container_class = set


class PMIDRRIDs(KeyAccessor):
    prop = 'pmid'
    object_container_class = RRIDSimple


class DOIRRIDs(KeyAccessor):
    prop = 'doi'
    object_container_class = RRIDSimple


class MPP(KeyAccessor):
    prop = 'uri_normalized'
    object_container_class = PMIDRRIDs


class MPD(KeyAccessor):
    prop = 'uri_normalized'
    object_container_class = DOIRRIDs
