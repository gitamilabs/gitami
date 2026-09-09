from tree_sitter import Tree, Node
from src.parsing.extractors.base import BaseExtractor
from src.parsing.models import (
    ParseResult,
    SymbolNode,
    CallEdge,
    ImportEdge,
    HeritageEdge,
    SymbolKind,
)


class PythonExtractor(BaseExtractor):
    """AST symbol, call, inheritance, and import extractor for Python code."""

    def __init__(self):
        super().__init__(language="python")

    def extract(self, tree: Tree, code_bytes: bytes, file_path: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language="python")
        if not tree.root_node:
            return result

        self._traverse_node(
            node=tree.root_node,
            code_bytes=code_bytes,
            file_path=file_path,
            result=result,
            parent_scope=[],
        )
        return result

    def _traverse_node(
        self,
        node: Node,
        code_bytes: bytes,
        file_path: str,
        result: ParseResult,
        parent_scope: list[str],
    ) -> None:
        """Recursively walk nodes to extract symbols, calls, inheritance, and imports."""

        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                symbol_name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                is_class = node.type == "class_definition"

                file_name = file_path.replace("\\", "/").split("/")[-1]
                is_test = (
                    symbol_name.startswith("test_")
                    or file_name.startswith("test_")
                    or file_name.endswith("_test.py")
                ) and not is_class

                if is_class:
                    kind: SymbolKind = "class"
                elif is_test:
                    kind: SymbolKind = "test"
                elif parent_scope:
                    kind: SymbolKind = "method"
                else:
                    kind: SymbolKind = "function"

                parent_class = parent_scope[-1] if parent_scope and not is_class else None
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"

                # Extract signature line (or parameters)
                sig_text = code_bytes[node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                params_node = node.child_by_field_name("parameters")
                if params_node:
                    sig_text += code_bytes[params_node.start_byte:params_node.end_byte].decode("utf-8", errors="ignore")

                # Extract docstring if present
                docstring = self._extract_docstring(node, code_bytes)

                # Extract full source code body
                code_body = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

                superclasses: list[str] = []
                if is_class:
                    superclasses_node = node.child_by_field_name("superclasses")
                    if superclasses_node:
                        for child in superclasses_node.children:
                            if child.type in ("identifier", "attribute"):
                                sc_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
                                if sc_name:
                                    superclasses.append(sc_name)
                                    result.heritage.append(
                                        HeritageEdge(
                                            subclass_name=symbol_name,
                                            target_name=sc_name,
                                            kind="extends",
                                            file_path=file_path,
                                            line=node.start_point[0] + 1,
                                        )
                                    )

                symbol = SymbolNode(
                    name=symbol_name,
                    kind=kind,
                    file_path=file_path,
                    language="python",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=sig_text.strip(),
                    docstring=docstring,
                    code_body=code_body.strip(),
                    qualified_name=qualified_name,
                    class_name=parent_class,
                    superclasses=superclasses,
                )
                result.symbols.append(symbol)

                # Recurse children with updated parent_scope
                new_scope = parent_scope + [symbol_name]
                for child in node.children:
                    self._traverse_node(child, code_bytes, file_path, result, new_scope)
                return

        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee_name = code_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", errors="ignore")
                caller_symbol = f"{file_path}::{'.'.join(parent_scope)}" if parent_scope else f"{file_path}::<module>"
                call_edge = CallEdge(
                    caller_symbol=caller_symbol,
                    callee_name=callee_name,
                    file_path=file_path,
                    line=node.start_point[0] + 1,
                )
                result.calls.append(call_edge)

        elif node.type in ("import_statement", "import_from_statement"):
            imports = self._extract_imports_from_node(node, code_bytes, file_path)
            result.imports.extend(imports)

        # Walk child nodes for non-definition / non-leaf containers
        for child in node.children:
            self._traverse_node(child, code_bytes, file_path, result, parent_scope)

    def _extract_docstring(self, node: Node, code_bytes: bytes) -> str:
        body_node = node.child_by_field_name("body")
        if not body_node:
            return ""
        for child in body_node.children:
            if child.type == "expression_statement":
                str_child = child.child(0)
                if str_child and str_child.type == "string":
                    return code_bytes[str_child.start_byte:str_child.end_byte].decode("utf-8", errors="ignore").strip("\"'\n ")
        return ""

    def _extract_imports_from_node(self, node: Node, code_bytes: bytes, file_path: str) -> list[ImportEdge]:
        import_edges = []
        line = node.start_point[0] + 1
        if node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
                    import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=name, module_path=name, line=line))
        elif node.type == "import_from_statement":
            module_name = ""
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module_name = code_bytes[module_node.start_byte:module_node.end_byte].decode("utf-8", errors="ignore")

            for child in node.children:
                if child.type in ("dotted_name", "aliased_import", "identifier") and child != module_node:
                    sym_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
                    if sym_name not in ("import", "from"):
                        import_edges.append(
                            ImportEdge(
                                importer_file=file_path,
                                imported_symbol=sym_name,
                                module_path=module_name,
                                line=line,
                            )
                        )
        return import_edges
