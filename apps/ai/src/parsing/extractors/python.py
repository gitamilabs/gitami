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
        decorators: list[str] = None,
    ) -> None:
        """Recursively walk nodes to extract symbols, calls, inheritance, and imports."""
        decorators = decorators or []

        # 1. Decorated definitions (@app.route, @bot.command, @tasks.loop, etc.)
        if node.type == "decorated_definition":
            decs = []
            for child in node.children:
                if child.type == "decorator":
                    decs.append(code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore").strip())
                    # Extract calls occurring inside the decorator (e.g. @tasks.loop(minutes=1))
                    for dec_child in child.children:
                        if dec_child.type == "call":
                            self._traverse_node(dec_child, code_bytes, file_path, result, parent_scope)
            defn = node.child_by_field_name("definition")
            if defn:
                self._traverse_node(defn, code_bytes, file_path, result, parent_scope, decorators=decs)
            return

        # 2. Function definitions and Class definitions
        elif node.type in ("function_definition", "class_definition"):
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
                elif any("route" in d.lower() or "endpoint" in d.lower() for d in decorators):
                    kind: SymbolKind = "router"
                elif parent_scope:
                    kind: SymbolKind = "method"
                else:
                    kind: SymbolKind = "function"

                parent_class = parent_scope[-1] if parent_scope and not is_class else None
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"

                # Extract signature line with decorators prepended if present
                sig_prefix = ("\n".join(decorators) + "\n") if decorators else ""
                sig_text = sig_prefix + code_bytes[node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
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

        # 3. Top-level module assignments (clients, bot instances, constants, app routers)
        elif node.type == "assignment" and not parent_scope:
            is_top_level = (
                node.parent is not None
                and node.parent.type == "expression_statement"
                and node.parent.parent is not None
                and node.parent.parent.type == "module"
            )
            if is_top_level:
                left_node = node.child_by_field_name("left")
                right_node = node.child_by_field_name("right")
                if left_node and left_node.type == "identifier":
                    symbol_name = code_bytes[left_node.start_byte:left_node.end_byte].decode("utf-8", errors="ignore")
                    if len(symbol_name) > 1 and not (symbol_name.startswith("__") and symbol_name.endswith("__")):
                        right_text = (
                            code_bytes[right_node.start_byte:right_node.end_byte].decode("utf-8", errors="ignore")
                            if right_node
                            else ""
                        )
                        kind: SymbolKind = "constant" if symbol_name.isupper() else "variable"
                        if any(fw in right_text for fw in ("Flask(", "FastAPI(", "APIRouter(")):
                            kind = "router"

                        code_body = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                        qualified_name = f"{file_path}::{symbol_name}"
                        sig_text = (
                            f"{symbol_name} = {right_text[:60]}"
                            if len(right_text) > 60
                            else f"{symbol_name} = {right_text}"
                        )

                        result.symbols.append(
                            SymbolNode(
                                name=symbol_name,
                                kind=kind,
                                file_path=file_path,
                                language="python",
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                signature=sig_text.strip(),
                                code_body=code_body.strip(),
                                qualified_name=qualified_name,
                            )
                        )
                # Traverse right side for calls inside the assignment value
                if right_node:
                    self._traverse_node(right_node, code_bytes, file_path, result, parent_scope)
                return

        # 4. Invocations and Call expressions
        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            caller_symbol = f"{file_path}::{'.'.join(parent_scope)}" if parent_scope else f"{file_path}::<module>"
            line = node.start_point[0] + 1

            if func_node:
                callee_name = code_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", errors="ignore")
                result.calls.append(
                    CallEdge(
                        caller_symbol=caller_symbol,
                        callee_name=callee_name,
                        file_path=file_path,
                        line=line,
                    )
                )

                # Attribute call target: e.g. check_reminders.start() -> also link check_reminders
                if func_node.type == "attribute":
                    obj_node = func_node.child_by_field_name("object")
                    if obj_node and obj_node.type == "identifier":
                        obj_name = code_bytes[obj_node.start_byte:obj_node.end_byte].decode("utf-8", errors="ignore")
                        if obj_name not in ("self", "cls") and len(obj_name) > 1:
                            result.calls.append(
                                CallEdge(
                                    caller_symbol=caller_symbol,
                                    callee_name=obj_name,
                                    file_path=file_path,
                                    line=line,
                                )
                            )

            # Inspect argument list for higher-order callables (e.g. run_in_executor(None, fetch_contests), Thread(target=run_web))
            args_node = node.child_by_field_name("arguments")
            if args_node:
                for arg in args_node.children:
                    if arg.type == "identifier":
                        arg_name = code_bytes[arg.start_byte:arg.end_byte].decode("utf-8", errors="ignore")
                        if arg_name not in ("True", "False", "None") and len(arg_name) > 1:
                            result.calls.append(
                                CallEdge(
                                    caller_symbol=caller_symbol,
                                    callee_name=arg_name,
                                    file_path=file_path,
                                    line=line,
                                )
                            )
                    elif arg.type == "keyword_argument":
                        kw_val = arg.child_by_field_name("value")
                        if kw_val:
                            if kw_val.type == "identifier":
                                val_name = code_bytes[kw_val.start_byte:kw_val.end_byte].decode("utf-8", errors="ignore")
                                if val_name not in ("True", "False", "None") and len(val_name) > 1:
                                    result.calls.append(
                                        CallEdge(
                                            caller_symbol=caller_symbol,
                                            callee_name=val_name,
                                            file_path=file_path,
                                            line=line,
                                        )
                                    )
                            elif kw_val.type == "attribute":
                                val_name = code_bytes[kw_val.start_byte:kw_val.end_byte].decode("utf-8", errors="ignore")
                                result.calls.append(
                                    CallEdge(
                                        caller_symbol=caller_symbol,
                                        callee_name=val_name,
                                        file_path=file_path,
                                        line=line,
                                    )
                                )

        # 5. Imports
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
                if child.type == "dotted_name":
                    name = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
                    import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=name, module_path=name, line=line))
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    if name_child:
                        name = code_bytes[name_child.start_byte:name_child.end_byte].decode("utf-8", errors="ignore")
                        import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=name, module_path=name, line=line))
        elif node.type == "import_from_statement":
            module_name = ""
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module_name = code_bytes[module_node.start_byte:module_node.end_byte].decode("utf-8", errors="ignore")

            for child in node.children:
                if child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    if name_child:
                        sym_name = code_bytes[name_child.start_byte:name_child.end_byte].decode("utf-8", errors="ignore")
                        import_edges.append(
                            ImportEdge(
                                importer_file=file_path,
                                imported_symbol=sym_name,
                                module_path=module_name,
                                line=line,
                            )
                        )
                elif child.type in ("dotted_name", "identifier") and child != module_node:
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
