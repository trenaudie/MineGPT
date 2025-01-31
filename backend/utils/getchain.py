from langchain.chains.chat_vector_db.prompts import (
    CONDENSE_QUESTION_PROMPT, QA_PROMPT)

from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import ConversationalRetrievalChain

from langchain.chains import LLMChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT
from langchain.chat_models import ChatOpenAI
import os
import config


class CustomConversationalRetrievalChain(ConversationalRetrievalChain):

    """This custom class adds a filter argument to the similarity search call in the _get_docs() method."""

    def _get_docs(self, question: str, filter: dict = None) -> list:
        # Your custom implementation here
        custom_docs = self.retriever.vectorstore.similarity_search(
            query=question,
            top_k=5,
            include_metadata=True,
            filter=filter
        )
        return self._reduce_tokens_below_limit(custom_docs)

    def _call(self, inputs: dict[str], _filter: dict = None) -> dict[str]:
        print("calling conversational retrieval chain")
        question = inputs["question"]
        chat_history_str = inputs['chat_history']

        print("question", question)
        print("chat_history_str", chat_history_str)
        if chat_history_str:
            new_question = self.question_generator.run(
                question=question, chat_history=chat_history_str
            )
        else:
            new_question = question
        docs = self._get_docs(new_question, filter=_filter)
        if not docs:
            # this happens when the filtering is too strong
            print("no docs found")
            raise ValueError("No documents found for this question.")

        new_inputs = inputs.copy()
        new_inputs["question"] = new_question
        new_inputs["chat_history"] = chat_history_str
        self.combine_docs_chain.return_intermediate_steps = True
        answer, extradict = self.combine_docs_chain.combine_docs(docs, **new_inputs)
        print("answer", answer)
        print('extradict intermediate steps: ', extradict['intermediate_steps'])
        NotRelevantAnswer =  all("no relevant text" in text.lower() for text in extradict['intermediate_steps'])
        if NotRelevantAnswer:
            print('setting return source documents to false')
            self.return_source_documents = False
            docs= []
        try: 
            return {self.output_key: answer, "source_documents": docs}
        except ValueError:
            return {self.output_key: answer, "source_documents": docs}

    def __call__(
        self, inputs: dict, filter: dict = None, return_only_outputs: bool = False
    ) -> dict:
        """Run the logic of this chain and add to output if desired.

        Args:
            inputs: Dictionary of inputs, or single input if chain expects
                only one param.
            return_only_outputs: boolean for whether to return only outputs in the
                response. If True, only new keys generated by this chain will be
                returned. If False, both input keys and new keys generated by this
                chain will be returned. Defaults to False.

        """
        #  {
        #   "$or": [{ "genre": { "$eq": "drama" } }, { "year": { "$gte": 2020 } }]
        # }
    

        filter_or = {"$or": [{'sid': config.Config.SID_DEFAULT}, {'sid': filter['sid']}]}
        inputs = self.prep_inputs(inputs)
        self.callback_manager.on_chain_start(
            {"name": self.__class__.__name__},
            inputs,
            verbose=self.verbose,
        )
        try:
            outputs = self._call(inputs, _filter=filter_or)
        except (KeyboardInterrupt, Exception) as e:
            self.callback_manager.on_chain_error(e, verbose=self.verbose)
            raise e
        self.callback_manager.on_chain_end(outputs, verbose=self.verbose)
        try:
            return self.prep_outputs(inputs, outputs, return_only_outputs)
        except ValueError:
            return outputs


def createchain_with_filter(vectorstore):
    """Create a ConversationalRetrievalChain for question/answering."""
    llm = ChatOpenAI(
        openai_api_key=os.environ['OPENAI_API_KEY'],
        temperature=0,
        model_name='gpt-3.5-turbo'
    )

    # 1. question + history -> question2
    question_generator = LLMChain(llm=llm, prompt=CONDENSE_QUESTION_PROMPT)
    # 1. q2 (+ history?) + sources -> [answers with sources] ->  one answer with sources
    doc_chain = load_qa_with_sources_chain(llm, chain_type="map_reduce")
    doc_chain.return_intermediate_steps = True

    chain = CustomConversationalRetrievalChain(
        retriever=vectorstore.as_retriever(),
        question_generator=question_generator,
        combine_docs_chain=doc_chain,
        return_source_documents=True)
    return chain
