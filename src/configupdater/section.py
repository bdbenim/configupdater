import sys
from typing import TYPE_CHECKING, Optional, Tuple, TypeVar, Union, overload

if sys.version_info[:2] >= (3, 9):
    from collections.abc import Iterator, MutableMapping

    List = list
    Dict = dict
else:
    from typing import Dict, Iterator, List, MutableMapping

if TYPE_CHECKING:
    from .document import Document

from .block import Block, Comment, Space
from .builder import BlockBuilder
from .container import Container
from .option import Option

T = TypeVar("T")
S = TypeVar("S", bound="Section")

ConfigContent = Union["Section", "Comment", "Space"]
SectionContent = Union["Option", "Comment", "Space"]
Value = Union["Option", str]


class Section(
    Block[ConfigContent], Container[SectionContent], MutableMapping[str, "Option"]
):
    """Section block holding options

    Attributes:
        name (str): name of the section
        updated (bool): indicates name change or a new section
    """

    def __init__(self, name: str, container: "Document"):
        self._container: "Document" = container
        self._name = name
        self._structure: List[SectionContent] = []
        self._updated = False
        super().__init__(container=container)

    def add_option(self: S, entry: "Option") -> S:
        """Add an Option object to the section

        Used during initial parsing mainly

        Args:
            entry (Option): key value pair as Option object
        """
        self._structure.append(entry)
        return self

    def add_comment(self: S, line: str) -> S:
        """Add a Comment object to the section

        Used during initial parsing mainly

        Args:
            line (str): one line in the comment
        """
        if isinstance(self.last_block, Comment):
            comment: Comment = self.last_block
        else:
            comment = Comment(container=self)
            self._structure.append(comment)

        comment.add_line(line)
        return self

    def add_space(self: S, line: str) -> S:
        """Add a Space object to the section

        Used during initial parsing mainly

        Args:
            line (str): one line that defines the space, maybe whitespaces
        """
        if isinstance(self.last_block, Space):
            space = self.last_block
        else:
            space = Space(container=self)
            self._structure.append(space)

        space.add_line(line)
        return self

    def _get_option_idx(self, key: str) -> int:
        return next(
            i
            for i, entry in enumerate(self._structure)
            if isinstance(entry, Option) and entry.key == key
        )

    def __str__(self) -> str:
        if not self.updated:
            s = super().__str__()
        else:
            s = "[{}]\n".format(self._name)
        for entry in self._structure:
            s += str(entry)
        return s

    def __repr__(self) -> str:
        return "<Section: {}>".format(self.name)

    def __getitem__(self, key: str) -> "Option":
        key = self._container.optionxform(key)
        try:
            return next(o for o in self.iter_options() if o.key == key)
        except StopIteration as ex:
            raise KeyError(f"No option `{key}` found", {"key": key}) from ex

    def __setitem__(self, key: str, value: Optional[Value] = None):
        if self._container.optionxform(key) in self:
            if isinstance(value, Option):
                if value.key != key:
                    raise ValueError(
                        f"Set key {key} does not equal option key {value.key}"
                    )
                idx = self.__getitem__(key).container_idx
                del self.structure[idx]
                self.structure.insert(idx, value)
            else:
                option = self.__getitem__(key)
                option.value = value
        else:
            if isinstance(value, Option):
                option = value
            else:
                option = Option(key, value, container=self)
                option.value = value
            self._structure.append(option)

    def __delitem__(self, key: str):
        try:
            idx = self._get_option_idx(key=key)
            del self._structure[idx]
        except StopIteration as ex:
            raise KeyError(f"No option `{key}` found", {"key": key}) from ex

    # MutableMapping[str, Option] for some reason accepts key: object
    # it actually doesn't matter for the implementation, so we omit the typing
    def __contains__(self, key) -> bool:
        """Returns whether the given option exists.

        Args:
            option (str): name of option

        Returns:
            bool: whether the section exists
        """
        return next((True for o in self.iter_options() if o.key == key), False)

    # Omit typing so it can represent any object
    def __eq__(self, other) -> bool:
        if isinstance(other, self.__class__):
            return self.name == other.name and self._structure == other._structure
        else:
            return False

    def __iter__(self) -> Iterator[str]:
        return (b.key for b in self.iter_blocks() if isinstance(b, Option))

    def iter_options(self) -> Iterator["Option"]:
        """Iterate only over option blocks"""
        return (entry for entry in self.iter_blocks() if isinstance(entry, Option))

    def option_blocks(self) -> List["Option"]:
        """Returns option blocks

        Returns:
            list: list of :class:`Option` blocks
        """
        return list(self.iter_options())

    def options(self) -> List[str]:
        """Returns option names

        Returns:
            list: list of option names as strings
        """
        return [option.key for option in self.iter_options()]

    has_option = __contains__

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Transform to dictionary

        Returns:
            dict: dictionary with same content
        """
        return {opt.key: opt.value for opt in self.iter_options()}

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = str(value)
        self._updated = True

    def set(self: S, option: str, value: Optional[str] = None) -> S:
        """Set an option for chaining.

        Args:
            option (str): option name
            value (str): value, default None
        """
        option = self._container.optionxform(option)
        if option in self.options():
            self.__getitem__(option).value = value
        else:
            self.__setitem__(option, value)
        return self

    @overload
    def get(self, key: str) -> Optional["Option"]:
        ...

    @overload
    def get(self, key: str, default: T) -> Union["Option", T]:
        ...

    def get(self, key, default=None):
        """This method works similarly to :meth:`dict.get`, and allows you
        to retrieve an option object by its key.
        """
        return next((o for o in self.iter_options() if o.key == key), default)

    # The following is a pragmatic violation of Liskov substitution principle
    # For some reason MutableMapping.items return a Set-like object
    # but we want to preserve ordering
    def items(self) -> List[Tuple[str, "Option"]]:  # type: ignore[override]
        """Return a list of (name, option) tuples for each option in
        this section.

        Returns:
            list: list of (name, :class:`Option`) tuples
        """
        return [(opt.key, opt) for opt in self.option_blocks()]

    def insert_at(self, idx: int) -> "BlockBuilder":
        """Returns a builder inserting a new block at the given index

        Args:
            idx (int): index where to insert
        """
        return BlockBuilder(self, idx)