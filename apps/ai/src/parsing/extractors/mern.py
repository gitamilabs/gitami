from tree_sitter import Tree, Node
from src.parsing.extractors.base import BaseExtractor
from src.parsing.models import (
    ParseResult,
    SymbolNode,
    CallEdge,
    ImportEdge,
    HeritageEdge,
    SymbolKind,
    LanguageType,
)


class MernExtractor(BaseExtractor):
    """AST symbol, call, inheritance, and import extractor for JS/TS/JSX/TSX code."""

    def __init__(self, language: LanguageType = "typescript"):
        super().__init__(language=language)

    def extract(self, tree: Tree, code_bytes: bytes, file_path: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=self.language)
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

    def _get_text(self, node: Node, code_bytes: bytes) -> str:
        return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def _traverse_node(
        self,
        node: Node,
        code_bytes: bytes,
        file_path: str,
        result: ParseResult,
        parent_scope: list[str],
    ) -> None:
        """Recursively walk tree nodes for JS/TS constructs."""

        # 1. Function declarations, Class declarations & Methods
        if node.type in ("function_declaration", "class_declaration", "method_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                symbol_name = self._get_text(name_node, code_bytes)
                is_class = node.type == "class_declaration"
                is_component = not is_class and symbol_name[:1].isupper()
                is_test = (
                    symbol_name.startswith("test")
                    or file_path.endswith((".test.ts", ".test.js", ".test.tsx", ".test.jsx", ".spec.ts", ".spec.js"))
                ) and not is_class

                if is_class:
                    kind: SymbolKind = "class"
                elif is_test:
                    kind: SymbolKind = "test"
                elif is_component:
                    kind: SymbolKind = "component"
                elif parent_scope:
                    kind: SymbolKind = "method"
                else:
                    kind: SymbolKind = "function"

                parent_class = parent_scope[-1] if parent_scope and not is_class else None
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"

                sig_text = self._get_text(name_node, code_bytes)
                params_node = node.child_by_field_name("parameters")
                if params_node:
                    sig_text += self._get_text(params_node, code_bytes)

                code_body = self._get_text(node, code_bytes)

                superclasses: list[str] = []
                interfaces: list[str] = []

                # Extract class inheritance & implementation
                if is_class:
                    for child in node.children:
                        if child.type == "class_heritage":
                            for h_child in child.children:
                                if h_child.type == "extends_clause":
                                    for target in h_child.children:
                                        if target.type in ("identifier", "type_identifier"):
                                            sc_name = self._get_text(target, code_bytes)
                                            if sc_name and sc_name != "extends":
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
                                elif h_child.type == "implements_clause":
                                    for target in h_child.children:
                                        if target.type in ("type_identifier", "identifier"):
                                            if_name = self._get_text(target, code_bytes)
                                            if if_name and if_name != "implements":
                                                interfaces.append(if_name)
                                                result.heritage.append(
                                                    HeritageEdge(
                                                        subclass_name=symbol_name,
                                                        target_name=if_name,
                                                        kind="implements",
                                                        file_path=file_path,
                                                        line=node.start_point[0] + 1,
                                                    )
                                                )

                symbol = SymbolNode(
                    name=symbol_name,
                    kind=kind,
                    file_path=file_path,
                    language=self.language,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=sig_text.strip(),
                    code_body=code_body.strip(),
                    qualified_name=qualified_name,
                    class_name=parent_class,
                    superclasses=superclasses,
                    interfaces=interfaces,
                )
                result.symbols.append(symbol)

                new_scope = parent_scope + [symbol_name]
                for child in node.children:
                    self._traverse_node(child, code_bytes, file_path, result, new_scope)
                return

        # 2. TypeScript interface declarations
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbol_name = self._get_text(name_node, code_bytes)
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"
                code_body = self._get_text(node, code_bytes)

                symbol = SymbolNode(
                    name=symbol_name,
                    kind="interface",
                    file_path=file_path,
                    language=self.language,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=f"interface {symbol_name}",
                    code_body=code_body.strip(),
                    qualified_name=qualified_name,
                )
                result.symbols.append(symbol)

                new_scope = parent_scope + [symbol_name]
                for child in node.children:
                    self._traverse_node(child, code_bytes, file_path, result, new_scope)
                return

        # 3. TypeScript type alias declarations
        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbol_name = self._get_text(name_node, code_bytes)
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"
                code_body = self._get_text(node, code_bytes)

                symbol = SymbolNode(
                    name=symbol_name,
                    kind="type",
                    file_path=file_path,
                    language=self.language,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=f"type {symbol_name} = ...",
                    code_body=code_body.strip(),
                    qualified_name=qualified_name,
                )
                result.symbols.append(symbol)
                return

        # 3. TypeScript enum declarations
        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbol_name = self._get_text(name_node, code_bytes)
                scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                qualified_name = f"{file_path}::{scope_path}"
                code_body = self._get_text(node, code_bytes)

                symbol = SymbolNode(
                    name=symbol_name,
                    kind="enum",
                    file_path=file_path,
                    language=self.language,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=f"enum {symbol_name}",
                    code_body=code_body.strip(),
                    qualified_name=qualified_name,
                )
                result.symbols.append(symbol)
                return

        # 4. Variable declarations (functions, schemas, tables, enums, routers, objects, constants)
        elif node.type in ("lexical_declaration", "variable_declaration"):
            is_const = "const" in self._get_text(node, code_bytes).split()[:2]
            for declarator in node.children:
                if declarator.type == "variable_declarator":
                    name_node = declarator.child_by_field_name("name")
                    value_node = declarator.child_by_field_name("value")

                    if not name_node:
                        continue

                    symbol_name = self._get_text(name_node, code_bytes).strip()
                    scope_path = ".".join(parent_scope + [symbol_name]) if parent_scope else symbol_name
                    qualified_name = f"{file_path}::{scope_path}"
                    code_body = self._get_text(declarator, code_bytes)

                    if value_node and value_node.type in ("arrow_function", "function_expression"):
                        is_component = symbol_name[:1].isupper()
                        is_test = (
                            symbol_name.startswith("test")
                            or file_path.endswith((".test.ts", ".test.js", ".test.tsx", ".test.jsx"))
                        )

                        if is_test:
                            kind = "test"
                        elif is_component:
                            kind = "component"
                        else:
                            kind = "function"

                        symbol = SymbolNode(
                            name=symbol_name,
                            kind=kind,
                            file_path=file_path,
                            language=self.language,
                            start_line=declarator.start_point[0] + 1,
                            end_line=declarator.end_point[0] + 1,
                            signature=f"const {symbol_name} = ...",
                            code_body=code_body.strip(),
                            qualified_name=qualified_name,
                        )
                        result.symbols.append(symbol)

                        new_scope = parent_scope + [symbol_name]
                        for child in value_node.children:
                            self._traverse_node(child, code_bytes, file_path, result, new_scope)

                    elif value_node and value_node.type == "call_expression":
                        fn_node = value_node.child_by_field_name("function")
                        fn_text = self._get_text(fn_node or value_node, code_bytes)
                        if any(k in fn_text for k in ("Table", "pgTable", "mysqlTable", "sqliteTable", "createTable", "model", "Schema")):
                            kind = "schema"
                        elif "Enum" in fn_text or "pgEnum" in fn_text:
                            kind = "enum"
                        elif "Router" in fn_text:
                            kind = "router"
                        elif "relations" in fn_text:
                            kind = "relation"
                        elif is_const:
                            kind = "constant"
                        else:
                            kind = "variable"

                        symbol = SymbolNode(
                            name=symbol_name,
                            kind=kind,
                            file_path=file_path,
                            language=self.language,
                            start_line=declarator.start_point[0] + 1,
                            end_line=declarator.end_point[0] + 1,
                            signature=f"const {symbol_name} = {fn_text}(...)",
                            code_body=code_body.strip(),
                            qualified_name=qualified_name,
                        )
                        result.symbols.append(symbol)

                        new_scope = parent_scope + [symbol_name]
                        for child in value_node.children:
                            self._traverse_node(child, code_bytes, file_path, result, new_scope)

                    elif value_node and value_node.type == "object":
                        kind = "router" if "router" in symbol_name.lower() else ("constant" if is_const else "variable")
                        symbol = SymbolNode(
                            name=symbol_name,
                            kind=kind,
                            file_path=file_path,
                            language=self.language,
                            start_line=declarator.start_point[0] + 1,
                            end_line=declarator.end_point[0] + 1,
                            signature=f"const {symbol_name} = {{...}}",
                            code_body=code_body.strip(),
                            qualified_name=qualified_name,
                        )
                        result.symbols.append(symbol)

                        # Walk object properties
                        new_scope = parent_scope + [symbol_name]
                        for child in value_node.children:
                            if child.type == "pair":
                                key_n = child.child_by_field_name("key")
                                val_n = child.child_by_field_name("value")
                                if key_n and val_n and val_n.type in ("arrow_function", "function_expression"):
                                    prop_name = self._get_text(key_n, code_bytes)
                                    prop_qname = f"{file_path}::{symbol_name}.{prop_name}"
                                    prop_sym = SymbolNode(
                                        name=prop_name,
                                        kind="method",
                                        file_path=file_path,
                                        language=self.language,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1,
                                        signature=f"{prop_name}: (...) => ...",
                                        code_body=self._get_text(child, code_bytes).strip(),
                                        qualified_name=prop_qname,
                                        class_name=symbol_name,
                                    )
                                    result.symbols.append(prop_sym)
                                    for sub_c in val_n.children:
                                        self._traverse_node(sub_c, code_bytes, file_path, result, new_scope + [prop_name])
                                else:
                                    self._traverse_node(child, code_bytes, file_path, result, new_scope)
                            else:
                                self._traverse_node(child, code_bytes, file_path, result, new_scope)

                    elif not parent_scope:
                        # Top-level constant/variable declaration
                        kind = "constant" if is_const else "variable"
                        symbol = SymbolNode(
                            name=symbol_name,
                            kind=kind,
                            file_path=file_path,
                            language=self.language,
                            start_line=declarator.start_point[0] + 1,
                            end_line=declarator.end_point[0] + 1,
                            signature=f"const {symbol_name}",
                            code_body=code_body.strip(),
                            qualified_name=qualified_name,
                        )
                        result.symbols.append(symbol)
                        if value_node:
                            new_scope = parent_scope + [symbol_name]
                            for child in value_node.children:
                                self._traverse_node(child, code_bytes, file_path, result, new_scope)

        # 5. Function/method calls and test runners (it, test, describe)
        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                raw_callee = self._get_text(func_node, code_bytes).strip()
                clean_callee = " ".join(raw_callee.split())
                caller_symbol = f"{file_path}::{'.'.join(parent_scope)}" if parent_scope else f"{file_path}::<module>"

                # Capture test runner invocations (e.g. it('should fetch', ...), test('works', ...))
                if clean_callee in ("it", "test", "describe"):
                    args_node = node.child_by_field_name("arguments")
                    test_desc = ""
                    if args_node and args_node.children:
                        for a in args_node.children:
                            if a.type in ("string", "string_fragment"):
                                test_desc = self._get_text(a, code_bytes).strip("\"'`")
                                break
                    test_label = f"{clean_callee}:{test_desc}" if test_desc else f"{clean_callee}_{node.start_point[0] + 1}"
                    symbol = SymbolNode(
                        name=test_label,
                        kind="test",
                        file_path=file_path,
                        language=self.language,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=f"{clean_callee}('{test_desc}')",
                        code_body=self._get_text(node, code_bytes),
                        qualified_name=f"{file_path}::{test_label}",
                    )
                    result.symbols.append(symbol)

                # Member method calls and chained expressions (e.g. ApiResponse.success(...) -> ApiResponse.success and .success())
                if func_node.type == "member_expression":
                    prop_node = func_node.child_by_field_name("property")
                    obj_node = func_node.child_by_field_name("object")
                    prop_name = self._get_text(prop_node, code_bytes).strip() if prop_node else ""
                    obj_name = self._get_text(obj_node, code_bytes).strip() if obj_node else ""

                    if obj_node and obj_node.type == "identifier" and prop_name:
                        result.calls.append(
                            CallEdge(
                                caller_symbol=caller_symbol,
                                callee_name=f"{obj_name}.{prop_name}",
                                file_path=file_path,
                                line=node.start_point[0] + 1,
                            )
                        )
                    if prop_name and len(prop_name) > 1 and not prop_name.startswith("_"):
                        result.calls.append(
                            CallEdge(
                                caller_symbol=caller_symbol,
                                callee_name=f".{prop_name}()",
                                file_path=file_path,
                                line=node.start_point[0] + 1,
                            )
                        )
                elif func_node.type == "identifier":
                    # Direct call: e.g. express(), pgTable(), relations(), drizzle()
                    result.calls.append(
                        CallEdge(
                            caller_symbol=caller_symbol,
                            callee_name=clean_callee,
                            file_path=file_path,
                            line=node.start_point[0] + 1,
                        )
                    )
                elif clean_callee and not "\n" in clean_callee and len(clean_callee) < 60:
                    result.calls.append(
                        CallEdge(
                            caller_symbol=caller_symbol,
                            callee_name=clean_callee,
                            file_path=file_path,
                            line=node.start_point[0] + 1,
                        )
                    )

        # 6. Import statements
        elif node.type in ("import_statement",):
            imports = self._extract_imports(node, code_bytes, file_path)
            result.imports.extend(imports)

        # Walk children for containers
        for child in node.children:
            self._traverse_node(child, code_bytes, file_path, result, parent_scope)

    def _extract_imports(self, node: Node, code_bytes: bytes, file_path: str) -> list[ImportEdge]:
        import_edges = []
        line = node.start_point[0] + 1
        module_path = ""
        source_node = node.child_by_field_name("source")
        if source_node:
            module_path = self._get_text(source_node, code_bytes).strip("\"'")

        clause_node = None
        for child in node.children:
            if child.type == "import_clause":
                clause_node = child
                break

        if not clause_node:
            if module_path:
                import_edges.append(ImportEdge(importer_file=file_path, imported_symbol="*", module_path=module_path, line=line))
            return import_edges

        for child in clause_node.children:
            if child.type == "identifier":
                sym_name = self._get_text(child, code_bytes)
                import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=sym_name, module_path=module_path, line=line))
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        name_n = spec.child_by_field_name("name")
                        if name_n:
                            sym_name = self._get_text(name_n, code_bytes)
                            import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=sym_name, module_path=module_path, line=line))
            elif child.type == "namespace_import":
                for id_n in child.children:
                    if id_n.type == "identifier":
                        sym_name = self._get_text(id_n, code_bytes)
                        import_edges.append(ImportEdge(importer_file=file_path, imported_symbol=sym_name, module_path=module_path, line=line))

        return import_edges
